# gnn/ 架构说明（v1，2026-10-22）

> 由复核子任务整理、主 agent 精简入库。代码在 `gnn/msgnn/`，本文件只讲结构与接口。

## 1 分层（单向依赖，无环）

    config ← data ← physics ← models ← losses ← experiment ← train / evaluate / predict ← scripts / tests

| 层 | 职责 | 关键文件 |
|---|---|---|
| 配置 | 9 个 dataclass，未知键硬报错 | `config.py` |
| 数据 | 磁盘契约、快照、切分、图、批次 | `data/{dataset,build_graph,normalizer}.py` |
| 物理 | 单元库 Γ、可微矢量远场算子、M0 基线 | `physics/{unit_library,radiation,baseline}.py` |
| 模型 | 编码器、消息传递、残差 GNN、CNN 对照 | `models/*.py` |
| 训练/评估 | 损失、循环、推理、指标 | `losses.py, train.py, evaluate.py, predict.py` |

**核心设计**：网络不直接输出方向图，只输出每个单元的复反射系数 q；方向图由无参数、可微、可自检的物理算子给出。
M0/M2/M3 共用同一条物理链路，M1 是唯一绕过物理的对照。

## 2 形状约定

| 符号 | 含义 | 值 |
|---|---|---|
| N | 物理单元数 | 400（20×20） |
| E | 有向边数（radius=1） | 2964 |
| M | 角点数 | 8280（θ 0–90 步 2°，φ 0–358 步 2°） |
| B | batch | 8 |
| 节点特征 | 9 维 | bit / 2bit−1 / x/λ / y/λ / ReΓ / ImΓ / |Γ| / boundary / nz |
| 边特征 | 5 维 | dx/λ / dy/λ / r/λ / cos az / sin az |

复场一律拆实部/虚部两路，避开 PyTorch 复数 autograd 的共轭约定。

## 3 物理算子

    S(s) = Σ_n q_n exp[j k (r_n · s)]        s = (sinθcosφ, sinθsinφ, cosθ)
    Eθ = C pθ S,  Eφ = C pφ S,  σ = |Eθ|² + |Eφ|²  [m²],  dBsm = 10 log10 σ
    C = 2√π/λ · P² · 1e-3                    (mm → m)
    vector: pθ = cosθcosφ, pφ = −sinφ    scalar: pθ = cosθ, pφ = 0

全 1 口径 → `4πA²/λ² = 19.34200583535 dBsm`（PEC 平板自检，写在 `tests/test_radiation.py`）。
核 `(M,N)` 预计算并分块，CPU 友好。

## 4 四个模型

| | q 的来源 | 物理算子 | 初始状态 | 回答的问题 |
|---|---|---|---|---|
| M0 | 单元库 Γ(bit) | ✔ | — | 局部基线在哪 |
| M1 | —（CNN 直接出 σ_dB） | ✘ | sky 偏置 | 纯数据能学到什么 |
| M2 | GNN head 直接出 q | ✔ | 随机弱口径 | 没有基线先验会怎样 |
| M3 | `q0 + Δq + b` | ✔ | **严格等于 M0**（零初始化头） | 残差修正是否有效 |

M3 的 `b` 是每样本一个复数（mean-pool 图嵌入），对应理论中"与编码正交的均匀共同模 |b|≈0.37"；
`Δq` 是逐单元修正。二者分离，正好回答"全局标量够不够、逐单元修正是否必要"。

## 5 损失

    L = Σ w · [c · asinh(Δ/c)]² / (B Σ w),   Δ = pred − targ,  c = 3 dB
    w = (sinθ + 0.2) · (3 if θ < 6° else 1)，归一化到 mean 1

- `sinθ` 防止极点过采样；`+0.2` 地板保证 θ=0 不被抹掉；`×3` 主瓣乘子把镜面点从 0.24 拉回 0.73（主瓣锥约占 5.6% 权重）。
- asinh 压缩：30 dB 失配与 3 dB 典型误差的损失比从 100× 降到 11.6×，梯度从 60 降到 1.79 —— 镜面样本不再主导。
- `compression="none"` 可关；`complex` 模式用逐方向相对误差 + 能量地板。

## 6 评估（三元组）

| 指标 | 定义 | 回答的问题 |
|---|---|---|
| `rho_lin` | 全前向半球线性功率 Pearson | 镜面缺口补上没有 |
| `rho_db` | θ∈[6,90]、实测 > −30 dBsm 的 dB Pearson | 弥散结构对不对 |
| `bias_db` | 同一 mask 的平均偏差 | 绝对电平偏多少 |

外加 RMSE 与 5 个角带（0–5 / 5–15 / 15–30 / 30–60 / 60–90°）。

**口径警告**：θ=90° 处 scalar 投影恒为 0，会让 6–90° 的 RMSE 失真（M0：6–60° 的 2.81 → 6–90° 的 6.50）。
正式报告建议同时给 6–60° 一行，与 `theory/` 的 ρ≈0.93 对得上。

## 7 防泄漏三件套

1. 快照 `snapshot.json` 冻结文件清单（sha256）；
2. 按 `layout_id` 分组切分，同布局不跨集；
3. Normalizer 只在 train 上 fit；早停与选模型只看 val。

## 8 已修问题（2026-10-22）

- `losses.py` 的 `..config` 越界（阻断）、`bits` 未转 tensor（阻断）、batch 维度（阻断）；
- 排列测试未换 pos、dtype 冲突、`fit_global_scalar` 虚部符号；
- 4 处测试断言（全局尺度、按图切片、常量列、精确板值）；
- `--snapshot` 训练的 run 现在会把快照复制进 run 目录（evaluate 可直接复现）。

## 9 仍待运行验证

pytest 全绿、smoke < 5 min、M0/M2/M3 的 `metrics.csv`、Δq 与 |b| 统计、压缩 on/off 两条曲线。
受"本机不执行代码"限制，这些尚未产生。
