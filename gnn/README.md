# msgnn —— 编码超表面散射场的物理引导 GNN（20x20 1-bit，10 GHz）

把「单元响应库 → 局部物理基线 → 图网络残差 → 可微矢量远场」这条链做成可运行、可复现的代码。
数据是 CST 全波仿真的 2° 网格远场（8280 点，幅度），当前 240+ 例随机编码。

**当前状态**：代码完整；按用户要求 **未在本机执行**（未跑 pytest / smoke / 训练），
详见 REPORT.md 第 0 节。首次运行请按下面的顺序执行并核对 REPORT 第 10 节的自检数字。

---

## 1 安装

    # Python 3.13 (Anaconda)，CPU 版 torch 足够
    python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    python -m pip install pyyaml numpy scipy pytest
    python -c "import torch; print(torch.__version__)"

不依赖 DGL / PyG：消息传递是手写的（scatter-add），图批处理是一维 index 偏移。

## 2 目录

    gnn/
      msgnn/
        config.py               dataclass + YAML 加载/校验（未知键直接报错）
        experiment.py           snapshot -> cases -> splits -> datasets -> 算子 -> 模型
        data/dataset.py         ff/res 解析、快照、目标、划分
        data/build_graph.py     节点/边特征、图批处理、GraphDataset
        data/normalizer.py      只用训练集拟合的标准化
        physics/unit_library.py 状态 -> 复反射（含角度插值扩展位）
        physics/radiation.py    可微矢量远场算子（torch）+ 逐点 numpy 参考
        physics/baseline.py     q0 / M0 / 全局标量 oracle 拟合
        models/                 encoders / message_passing / residual_gnn / cnn_baseline / pipeline
        losses.py               power / complex 两种损失 + 动态范围压缩
        train.py evaluate.py predict.py inference.py
      configs/                  train_m3.yaml / train_m2.yaml / baseline_m1.yaml
      scripts/                  make_splits.py / run_baselines.py / smoke_test.py
      tests/                    test_radiation.py / test_graph.py / test_dataset.py
      README.md REPORT.md

## 3 快速开始

    cd D:/GNN/gnn

    # 0) 测试（应全过；含 19.342 dBsm 自检、torch 与 numpy 的 1e-6 对齐、排列等变）
    pytest tests/ -q

    # 1) 冒烟：8 例 2 epoch，必须 < 5 min
    python scripts/smoke_test.py

    # 2) 冻结文件清单 + 划分（写 runs/snapshot.json 与 runs/splits.json）
    python scripts/make_splits.py --out runs/splits.json

    # 3) 训练（M3 / M2 / M1 各一个种子；M0 无需训练）
    python -m msgnn.train --config configs/train_m3.yaml --seed 0 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_s0
    python -m msgnn.train --config configs/train_m2.yaml --seed 0 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m2_s0
    python -m msgnn.train --config configs/baseline_m1.yaml --seed 0 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m1_s0

    # 4) 评估：三元组 + 分带 -> runs/metrics.csv, runs/metrics_summary.csv
    python -m msgnn.evaluate --runs runs/m3_s0 runs/m2_s0 runs/m1_s0 m0 m0g \
        --out runs --splits val,test

    # 5) 单例预测（复场 + q，可直接和 q0 对比）
    python -m msgnn.predict --run runs/m3_s0 --case 0 --out runs/m3_s0/pred_0000.npz

每个 run 目录里会有：config.yaml / snapshot.json / splits.json / normalizer.json /
best.pt / last.pt / history.csv / summary.json。

## 4 数据契约

| 文件 | 内容 |
|---|---|
| D:/dataset/results/ff/ff_XXXX.txt | theta phi \|E_theta\|_dBsm \|E_phi\|_dBsm，2° 网格，theta 0..90（46）× phi 0..358（180）= 8280 行，theta 外层；**只有幅度** |
| D:/dataset/results/res_XXXX.json | code（100 字符 = 10×10 宏单元）、specular/mean_far/max、seed、block |
| D:/dataset/codes/code_XXXX.txt | 同上明文 |
| D:/ff_er265_r2_b2/ff_10.txt | 1° 网格 6 列（含相位），与 case 0000 同设计；complex 损失模式用它验证 |

- 单元：P = 14 mm，20×20，基板 er 2.65 / tanδ 0.0013 / 1.5 mm，PEC 地板，
  圆贴片 r = 4.7 mm(bit0) / 2.0 mm(bit1)；Gamma0 = 0.867∠−5.3°，Gamma1 = 0.852∠174.6°。
- 每个 bit 覆盖 2×2 个物理单元（BLOCK = 2），所以 10×10 码 -> 20×20 节点。
- **数据的可用性判据**：res_XXXX.json 存在（生成器先写 ff 再原子写 json），
  且 ff 的行数/角度网格与快照一致；否则跳过并记 warning。
- 快照（snapshot.json）记录每个 ff 的 sha256/size，训练期间新出现的 case 不会被拉进来。

## 5 配置要点

    physics.projection      vector（默认，E_theta/E_phi 双分量）/ scalar
    physics.gamma_source    floquet（0.867/0.852，默认）/ unit（|Gamma|=1，同相位）
    model.name              m0 | m1 | m2 | m3
    model.global_branch     M3 的每样本复标量 b（正交共同模），M2 必须关
    loss.mode               power（当前幅度数据）/ complex（6 列文件）
    loss.compression        asinh + compression_db=3（动态范围压缩，默认开）
    loss.angle_weight       solid_angle（w 正比 sin(theta)，floor=0.2 保证镜面不被权重抹掉）
    loss.mainlobe_boost     theta<6° 的额外权重（默认 3.0）
    runtime.threads         4（避免和 CST 抢 CPU）

## 6 约定（与 theory/ 一致，勿改）

    E_theta = C * cos(theta) cos(phi) * S
    E_phi   = -C * sin(phi) * S
    S       = sum_n q_n exp(j k r_n . s_hat)
    C       = 2 sqrt(pi)/lambda * P^2 * 1e-3
    sigma   = |E_theta|^2 + |E_phi|^2   [m^2] = dBsm
    全 1 口径 => sigma(0) = 4 pi A^2 / lambda^2 = 19.342 dBsm   <- 每个模型的必过自检

## 7 常见问题

- **torch 装不上**：本包没有 numpy 回退实现（手写反向传播无法在无执行环境里验证，
  见 REPORT 第 9 节）。若 pytorch 源不可达，先试清华镜像，再考虑
  conda install pytorch cpuonly -c pytorch。
- **OOM / 太慢**：runtime.threads 调小；runtime.dtype 用 float32；--max-train 限制样本。
- **复算指标不一致**：检查各 run 目录下的 snapshot.json 是否同一份 —— 不同快照 = 不同样本集。
- **Windows 路径**：YAML 里统一用正斜杠（D:/dataset），反斜杠在 YAML 里是转义字符。
