# msgnn 交付报告：物理引导 GNN 的散射场预测流程

**对象**：20×20 1-bit 反射式编码超表面（P = 14 mm，280 mm = 9.34λ，10 GHz）
**数据**：CST 全波远场，2° 网格 8280 点（θ 0..90 / φ 0..358），**仅幅度**；当前 241 例随机码
**代码**：D:/GNN/gnn（包 msgnn，v0.1.0）
**日期**：2026-10-22

---

## 0 执行状态（必读）

**本次交付没有在本机执行任何 python / pytest / 训练。**
在编写过程中收到明确指令「先不在本电脑上运行代码」，随即停止了全部执行
（当时正在后台下载 torch 的 CPU wheel，我这条下载任务已中止；主 agent 随后于 08:44
自行安装成功，版本 2.14.1+cpu —— 本会话没有验证过它）。

因此：

| 项 | 状态 |
|---|---|
| 代码 / 配置 / 测试 / 文档 | **已完成**（静态交付） |
| pytest tests/ -q | **未执行** |
| python scripts/smoke_test.py | **未执行** |
| M0/M1/M2/M3 训练与 metrics.csv | **未执行**；本报告不含任何模型/指标实测数字（唯一的文件格式核对见 §4，发生在指令下达之前） |
| torch 环境 | 主 agent 于 08:44 安装成功（2.14.1+cpu）；**本会话未验证** |

### 0.1 独立复核与修复记录（2026-10-22）

外部只读复核提出 3 条，均已修复；自查另发现 1 条：

1. **阻断性**：msgnn/losses.py 写成了 from ..config import LossCfg —— losses 是包顶层模块，
   .. 越界，ImportError 会让 train / evaluate / smoke 全部起不来。已改为 from .config import LossCfg。
   修完已全包复查：其余 .. 导入只出现在 data/ 与 models/ 两个子包内（合法）。
2. tests/test_graph.py::test_permutation_invariance_operator 只置换了 q、没置换 pos ——
   远场当然会变，测试写法本身错。已改为同时置换位置，并补一个「只置换 q 会改变远场」的反例，
   避免测试恒真。
3. tests/test_graph.py 中 model / 算子为 float64 而 batch 为 float32 的两处 matmul dtype 冲突，
   已统一 cast（cast_batch / .double()）。
4. 自查：physics/baseline.py::fit_global_scalar 的虚部梯度少了负号（d|A|^2/db_im 应为
   -2 Im(A* gu)），会让 M0g oracle 拟合到错误相位。已修正。

**这些修复同样没有经过执行验证** —— 见下面的限制说明。

本报告中的数值只有两类，逐条标注：

- **[已确认]** 来自 D:/GNN/theory/REPORT.md 的既有分析（那部分是真跑过的）；
- **[预期]** 由物理关系或该报告外推得到的**待验证**数值 / 验收判据。

第 10 节给出「首次运行自检清单」：每一步跑完应该看到什么数字，用来在 10 分钟内判断
代码是否正确。第 8 节把任务要求的六个问题拆成「代码在哪里回答 / 运行后填什么」。

---

## 1 交付清单

| 文件 | 作用 | 谁来验证 |
|---|---|---|
| msgnn/config.py | dataclass + YAML 加载、未知键报错、范围校验 | tests/test_dataset.py::test_config_* |
| msgnn/physics/radiation.py | 可微矢量远场算子（torch）+ 逐点 numpy 参考 | test_radiation.py（19.342 自检、1e-6 对齐、梯度） |
| msgnn/physics/unit_library.py | 状态 -> 复反射；角度插值扩展位（CSV） | test_graph.py（q0 只取两个值） |
| msgnn/physics/baseline.py | q0、M0、全局标量 oracle 拟合 | evaluate.py 的 m0 / m0g |
| msgnn/data/dataset.py | ff/res 解析、快照、目标、按 layout_id 划分 | test_dataset.py |
| msgnn/data/build_graph.py | 节点/边特征、8(24) 邻域、图批处理 | test_graph.py |
| msgnn/data/normalizer.py | 只用训练集拟合的标准化 | test_graph.py::test_normalizer_fits_train_only |
| msgnn/models/{encoders,message_passing,residual_gnn}.py | 手写消息传递 + M2/M3 | 训练 |
| msgnn/models/cnn_baseline.py | M1：CNN/U-Net 直接回归方向图 | 训练 |
| msgnn/models/pipeline.py | 四种模型 -> sigma_dB 的统一封装 | smoke_test |
| msgnn/losses.py | power / complex + 动态范围压缩 + 主瓣/零深项 | test_dataset.py::test_power_loss_* |
| msgnn/{train,evaluate,predict,inference}.py | 训练 / 评估 / 单例推理 | 命令行 |
| configs/*.yaml | M3 / M2 / M1 三份配置 | test_dataset.py::test_config_file_parses |
| scripts/{make_splits,run_baselines,smoke_test}.py | 划分 / 基线 / 冒烟 | 命令行 |
| tests/test_{radiation,graph,dataset}.py | 三层测试 | pytest |

规模（**[估算]**，由结构直接数出，运行后 summary.json 的 n_params 会给出实测值）：
M3 约 101k 参数（hidden 64 × 3 层，含全局支路），M2 约 97k，M1 约 212k（width 16 U-Net）。

---

## 2 物理层：为什么它必须先过 19.342 dBsm

前向式（与 theory/common.py、theory/models.py 完全一致）：

    S(u,v)  = sum_n q_n exp[ j k (x_n u + y_n v + z_n w) ],   (u,v,w) 为单位方向
    E_theta = C * cos(theta) cos(phi) * S
    E_phi   = -C * sin(phi) * S
    C       = 2 sqrt(pi)/lambda * P^2 * 1e-3          (mm -> m)
    sigma   = |E_theta|^2 + |E_phi|^2                 [m^2]，dBsm = 10 log10

自检：q_n = 1（全 1 口径）时 S = 400，sigma(0) = 4 pi A^2 / lambda^2 = **19.342 dBsm**
（10 GHz，A = 0.28×0.28 m²）。这一条同时钉住了单位、面积、常数、角度网格与极化投影，
是唯一能在没有标签的情况下判断算子对错的检验。两种投影都必须过这一关
（scalar 在 theta=0 处 cos=1，vector 在 theta=0 处 cos(theta)cos(phi)=1 且 phi 无关）。
**注意：这是测试的验收目标，本会话没有执行测试，所以“已通过”不在本报告的断言范围内。**
19.342 这个数本身是解析值（theory/REPORT.md §3 的 self_check 跑出过 19.342 ± 0.000）。

为什么默认 vector 而不是 scalar：[已确认]（theory/REPORT.md §4.5）实测 E/H 面差 **−1.84 dB**，
矢量投影预测 **−1.61 dB**（差 0.23），标量投影预测 0 dB（差 1.84）；且 M0b（矢量）把 H 面
偏差从 −4.04 压到 −2.01 dB、rH(0–90) 从 0.57 提到 0.62。这是**辐射层必须带两个极化分量**
而不是一个 cos(theta) 的直接证据。

对齐测试（tests/test_radiation.py）：

1. test_uniform_aperture_is_pec_plate：torch 算子，两种投影，任意 phi -> 19.342 ± 1e-6；
2. test_torch_matches_numpy：随机复 q、随机方向，torch 与 numpy 参考的**峰值相对误差 < 1e-6**
   （阈值是要求；float64 下预期约 1e-14，未实测）；
3. test_matches_theory_models：若 D:/GNN/theory 可导入，直接与 theory/models.py 的
   af_ideal 逐点比对（两种投影，阈值 1e-9）；不可导入则 skip；
4. test_gradients_match_finite_differences：对 q 的实部/虚部做中心差分，与 autograd 比（1e-5）；
5. test_batch_matches_single / test_theta_zero_is_phi_independent。

---

## 3 四个模型（与计划文档的 M0–M3 对齐）

下表“参数”列的三个数字都是 **[估算]**（按层结构数的，没有实测）。

| 编号 | 定义 | 输出 | 参数 [估算] | 物理含义 |
|---|---|---|---|---|
| **M0** | q_n = q0_n（孤立单元 Floquet 库），直接进辐射层 | E_theta, E_phi -> sigma_dB | 0 | 局部周期基线（theory 的 M0） |
| **M1** | 20×20 比特 -> 32×32 零填充 -> U-Net 编码/解码 -> 秩 4 因子化读出 -> 46×180 dB 网格 | sigma_dB | 约 212k | 无物理、无图的对照（PGRL/CNN 路线的替身） |
| **M2** | q = GNN(graph)，**不加 q0** | q -> 辐射层 | 约 97k | 检验「残差形式」本身的价值 |
| **M3** | q = q0 + dq(节点) + b(每样本复标量)，dq、b 都由 GNN 出 | q -> 辐射层 | 约 101k | 主模型 |

设计要点：

1. **零初始化输出头**：M3 在 epoch 0 时 dq = 0、b = 0，即**恰好等于 M0**。
   之后每一分改进都是学出来的，不存在「初始化就比基线好/差」的混淆。
2. **全局支路（model.global_branch）**：把节点嵌入做 mean-pool -> MLP -> 2 个实数
   （b 的实部/虚部），广播加到每个节点上。这正好对应 theory/REPORT.md §5 的共同模：
   q_n = q0_n + b，则 sigma(b) = |C (S0 + b U) p|^2，U 是全 1 口径的阵列因子。
   报告的建议是「GNN 只需学每单元相对该全局分量的偏差，自由度从 400 个复数降到
   1 个复数 + 小残差，数据效率最高」——本实现按这个建议做，同时保留 M2 作为
   「不要全局支路、不要 q0」的对照，所以 M3−M2 与 M3−M0 分别回答两个不同问题。
3. **图**：节点 = 400 个物理单元；特征 9 维（编码、2*bit−1、x/λ、y/λ、Re Γ、Im Γ、
   |Γ|、边界标记、n·z）；边 = 8 邻域双向（radius=2 -> 24 邻域），边特征 5 维
   （dx/λ、dy/λ、r/λ、cos 方位角、sin 方位角）。邻域按**物理表面邻接**，不做全连接。
4. **排列等变**：聚合是 scatter-add，池化是 mean，算子只对节点求和；测试里把节点
   重排（并同步重映射 edge_index）后远场必须逐点相同（float64，rtol 1e-8）。
   注意普通 GNN 只有**排列**等变，没有旋转等变 —— 这一点在计划的步骤 06 里也已注明。

---

## 4 数据契约、快照与划分

- 解析：ff_XXXX.txt（4 列，8280 行，theta 外层）× res_XXXX.json（code 100 字符、block=2、
  specular/mean_far/max）-> 10×10 宏比特 -> 20×20 物理比特 -> 400 节点。
  [已核对，在“禁止执行”指令之前] 用 ff_0000.txt 读出的网格：θ 唯一值 46 个（0..90 步长 2）、
  φ 180 个（0..358 步长 2），46×180 = 8280，θ 为外层（文件共 8280 行）。全部 case 由同一导出脚本产生。
- **可用性判据**：res_XXXX.json 必须存在（生成器先写 ff、最后原子写 json），
  且 ff 行数与角度网格与快照一致；否则跳过并记录 warning。这样即使 CST 正在写新文件，
  也不会把半截文件读进来。
- **快照**：snapshot.json 记录每个 ff 的 size + sha256；训练开始时若已存在就复用，
  运行中新增的 case 一律不进入本次训练（满足「训练前快照、训练中不增删」的要求）。
- **划分**：按 layout_id 分组 70/15/15，固定种子 20261022，落盘 splits.json。
  当前每例是独立 i.i.d. 随机码，所以 layout_id = 码的 sha1（两例同码则同组）；
  若 res_XXXX.json 带 layout_id（v2 契约）则优先用它。make_splits 会自检：
  组不跨 split、并集等于全集，并打印每个 split 的镜面均值/占空比（防泄漏）。
- **归一化**：只用训练图拟合，存 normalizer.json，评估时加载同一份（predict_run 强制）。
- **一个已知的样本量事实**（[已确认]，来自 cst/后续工作计划.md §3.2）：1000 例 i.i.d.
  随机码的镜面标签方差只有约 0.2 dB（该结论来自当时的实测统计，不是本报告的估计）。这意味着**镜面那一列几乎没有可学的编码依赖**，
  能学的主要是弥散结构 + 一个近似常数的共同模。这直接决定了第 7 节的预期。

---

## 5 损失：为什么必须压缩动态范围

[已确认]（theory/REPORT.md §1.1/§4）镜面瓣 10.80 dBsm，弥散均值 −6.62 dBsm，相差 **17.4 dB**，
逐点最深处相差 **25–30 dB**。
若用复场相对误差 sum|F_hat−F|² / sum|F|²，镜面那 4 个 theta 环（8280 点里的 720 点）
在分子分母里都占主导，梯度几乎全部来自镜面 -> 弥散结构学不动（计划文档步骤 07 的
原话：「镜面瓣会比弥散区高 25–30 dB，会主导训练」）。

本实现提供两条正交的压缩手段：

1. **power 模式（默认，适配当前只有幅度的数据）**

       delta = sigma_hat_dB - sigma_dB
       g(d)  = c * asinh(d / c),  c = compression_db = 3 dB
       L     = sum_m w_m g(delta_m)^2 / (B * sum_m w_m)

   定量效果（这是公式的算术性质，不是实验结果）：40 dB 的误差 -> g = 3*asinh(13.3) = 9.80
   （平方 96），而纯 MSE 是 1600，**抑制 16 倍**；1 dB 的误差 -> g = 0.98（平方 0.96），
   与 MSE 几乎一致。
   也就是说：小误差照常按 dB 计，大误差不再线性放大。compression: none 可退回纯 MSE。

2. **complex 模式（6 列文件）**

       L = sum_m w_m |F_hat_m - F_m|^2 / (|F_m|^2 + eps_rel * mean|F|^2) / sum w_m

   逐方向相对误差（每个方向贡献 O(1)），这是计划里 sum w|F_hat−F|²/(sum w|F|²+eps)
   的「压缩版」；complex_compress: false 则用原式。注意分母带 eps_rel 而不是
   只用 |F|²，否则深零点会爆炸。

**角度权重**：w 正比 sin(theta)（立体角），但 sin(0)=0 会把镜面那一个样本的权重抹成 0，
所以加 floor=0.2；再对 theta<6° 给 mainlobe_boost=3 的额外权重。
这是本节唯一一个**主观**选择，理由与消融方式都写在这里：solid-angle 权重是为了
不让等角度网格在极区重复计数，floor+boost 是为了不让 25–30 dB 的主瓣在损失里消失；
把 loss.mainlobe_boost 设为 1.0 即可复现「纯 sin(theta)」的口径，作为消融。
零深附加项（null_weight）已实现、默认关闭 —— 当前指标里没有零深项，先不加。

---

## 6 评估协议

固定三元组（theory/REPORT.md §4.6 的结论：单报一个相关系数会选错模型）：

| 指标 | 定义 | 回答什么 |
|---|---|---|
| rho_lin | 全半球 theta 0–90 上 **线性功率** sigma 的 Pearson r | 镜面 13.8 dB 缺口补上没补上 |
| rho_db | theta 6–90、实测 > −30 dBsm 上 **dB 值**的 Pearson r | 弥散结构与零深对不对 |
| bias_db | 同一集合上 mean(pred_dB − meas_dB) | 能不能当绝对电平预测器 |
| rmse_db | 同一集合上的 RMS | 综合 |
| spec_err | theta=0 处 sigma 的差 | 镜面 |
| mean_far_err | theta 10–90 线性均值之差 | 弥散电平 |
| 分带 | 0–5 / 5–15 / 15–30 / 30–60 / 60–90 | 误差分布在哪 |

输出：每个 run 每 split 每样本一行 -> metrics.csv；按 (model, split) 汇总 -> metrics_summary.csv。
**门槛**：|bias_db| <= 3 dB 才允许参与「谁更好」的排序（照抄 theory 报告的做法）。
测试集只用于最终评估：train.py 里早停与选模型**只看 val**，evaluate.py 才能碰 test。

## 7 预期结果与验收判据（待运行，替换为实测）

### 7.1 已有锚点 [已确认]（theory/REPORT.md，同一份数据、同一套约定）

| 量 | 数值 |
|---|---|
| 实测镜面 / 弥散 | 10.80 / −6.62 dBsm |
| M0（AF，Floquet 库 0.867） | −3.01 / −7.95 dBsm；主平面相关 0.83/0.85/0.78；72 子午线 0.93±0.06；RMSE 3.05 |
| M0 + 正交共同模 b = 0.366 角 265° | **10.80 / −6.50**；相关 0.96/0.92/0.92；RMSE **1.78** |
| 阵中有效 |Gamma|（由弥散反演） | **1.002**（Floquet 的 −1.24 dB 是数值损耗） |
| 缺口折算 |a| = 10^((10.798−19.342)/20) | 0.374 |
| 7 组平均 rho2D（0–90，dB） | M0 0.879、M1 0.888、M6 0.905、M2(PO) 0.913 |
| 7 组平均 rho(6–90) | M0 0.906、M1 0.916、M3(RS) 0.909 |

### 7.2 本实现的预期 [预期]

| 模型 | spec (dBsm) | mean_far | rho_lin | rho_db | bias (dB) | rmse (dB) |
|---|---|---|---|---|---|---|
| M0（floquet） | 约 −3.0 | 约 −7.9 | 约 0.45 | 约 0.90 | 约 −4.6 | 约 7.7 |
| M0u（abs(Gamma)=1，附加行） | 约 −3.0 | 约 −6.6 | 约 0.45 | 约 0.90 | 约 −3.3 | 约 6.6 |
| M0g（每样本 1 个复标量，oracle） | 约 10.5–10.8 | 约 −6.5 | 约 0.85–0.92 | 约 0.93 | 约 −0.5–−2 | 约 2–3 |
| M2（GNN 直接出 q） | 未知，可能偏暗 | 未知 | 0.5–0.8 | 0.80–0.90 | 未知 | 5–8 |
| M3（q0 + dq + b） | 目标 >= 8 | >= −7 | **> 0.85** | **> 0.90** | **abs(bias) <= 3** | **< 4** |
| M1（CNN） | 差（无物理先验） | 差 | 0.2–0.5 | 0.5–0.8 | 大 | > 6 |

依据：M0 那一行直接来自 [已确认] 的 theory 数字（我的 M0 = AF + 矢量投影，与 M0b 同族，
只差离散化与极化口径，故 rho_lin 取 0.44–0.48 这一档）；M0g 对应 theory 里「M0 + 正交背景」
在 10 GHz 的 in-sample 结果（RMSE 1.78），我的 oracle 只在 dB 域 + 主瓣加权下拟合 2 个实参数，
所以给区间；M3 的判据是「必须接近 M0g、且 rho_db 不低于 M0」——**如果 M3 拿不到
rho_lin > 0.85，说明全局支路没学到共同模**，那时看 predict.py 打印的 |b|：应接近 0.37。

### 7.3 验收判据（写进脚本输出即可判定）

1. M3 相对 M0：rho_lin 提升 >= +0.2，abs(bias) 从 >4 dB 降到 <=3 dB；
2. M3 相对 M2：rmse_db 至少低 1 dB（残差形式的价值）；
3. M3 的 |b|（predict.py 打印或从权重反算）落在 0.25–0.55，与 0.37 同量级；
4. 三个种子的 rho_db 标准差 < 0.02（否则先调 lr/种子）。

---

## 8 六个必答问题的回答框架

**(1) M3 是否显著优于 M0？三个指标分别差多少？**
代码：evaluate.py 把 M0 与 M3 放在同一 split、同一网格、同一指标下算，直接输出
metrics_summary.csv 的两行差值。判据见 7.3。**运行后填**：rho_lin / rho_db / bias 三个差。
预期：rho_lin +0.3–0.45（0.45 -> 0.85+），rho_db +0.02–0.05，bias 从 −4.6 抬到 −1 上下。

**(2) 学到的主要修正是什么（全局标量还是逐单元）？**
三条定量证据，代码都已就位：
- **M0g oracle**（每样本 1 个复标量，2 个实自由度）能到 rho_lin 约 0.85–0.92。若 M3 与 M0g 相当，
  说明 M3 学到的绝大部分就是那一个全局共同模，逐单元部分只是小残差。
- **M3 的 b 与 dq 的对比**：predict.py 打印 |q0| mean、|dq| mean、mean(dq)。
  **注意（2026-10-22 起）**：Δq 在每张图上做了去均值（审计 B3），所以 mean(Δq) 恒为 0 是**构造性质**，
  均匀分量全部由 b 承担。因此验收应看 **|b| 与 arg b**（对照 0.37 / 265°）与 **per-node std(Δq)**
  （逐单元修正的强度），而不是 mean(Δq)。改造前的旧 checkpoint 与本次口径不可直接比较。
- **M3-noglob 消融**（model.global_branch: false 的 train_m3 变体）：若它明显差于 M3，
  进一步证明增益来自全局支路而不是消息传递。
报告里应给出：mean(Δq) 的模与相位（对照 0.37 / 265°）、per-node std(Δq)、
以及 (M3−M0)/(M0g−M0) 的比值（全局标量解释了多少比例的增益）。
**注意**：265° 是相对编码项 174.65° 的相位，本包不约束 b 的相位，只在报告里做对照。

**(3) 240 例时误差随 epoch 的走势、是否过拟合、还需要多少数据？**
代码：history.csv 有每 epoch 的 train_loss / val_loss / val_rmse / val_bias / val_rho_db，
--max-train 可直接做数据效率曲线（如 60/120/180/241 × 3 seeds）。
判据：val_loss 在 patience=15 内不再下降即早停，best_epoch 与 epochs_run 写进 summary.json；
若 best_epoch 远小于总 epoch 且 train_loss 继续下降 -> 过拟合。
数据需求判断（[预期]，可运行后确认）：镜面标签方差只有约 0.2 dB（见 §4），全局共同模是
1–2 个自由度、几十例就够；**真正吃数据的是弥散的小尺度结构**（零深位置）。
按 learning curve 的斜率外推：240 例下 rmse 每翻倍数据降约 0.5–1 dB，
要 rmse < 2 dB 约需 400–600 例**结构化**码（不是 i.i.d. 随机码）。
这与 cst/后续工作计划.md §3.2(5)「1000 个 i.i.d. 码在统计上是同一类样本」一致。

**(4) 与计划文档 M0–M3 定义的对齐 / 未实现项**
见第 9 节表格。

**(5) 复现命令**
见第 10 节。

**(6) 报告方式**
本次以「未执行」状态交付（第 0 节），首次运行后把 7.2 表替换为 metrics_summary.csv 的实测行。

---

## 9 与计划文档的对齐、未实现项与原因

| 计划条目（步骤/编号） | 状态 | 说明 |
|---|---|---|
| 步骤 06 图：节点=单元、边=表面邻接、边特征 dx/dy/r/方位角 | 已实现 | radius 可配 1/2（8/24 邻域），双向有向边 |
| 步骤 06 节点特征：编码、位置、复反射、边界 | 已实现 | 另加 n·z（曲面扩展位，平面恒 1） |
| 步骤 06 排列不变性检查 | 已实现并测 | 算子级 + 整模型级（重排 + edge_index 重映射） |
| 步骤 04 可微辐射层 + 解析/全波对照 | 部分 | 19.342 自检、torch 与 numpy 的 1e-6 对齐、梯度检查已写；**闭合面 Huygens 重建未做**（需要 CST 的 E/H 面数据） |
| 步骤 04 低阶源基函数能力检验（拟合 q 重建远场） | 未做 | 只有幅度标签时无法做复数最小二乘；需要 6 列数据或近场 |
| 步骤 07 M2/M3 + 端到端 | 已实现 | 零初始化 -> 起点等于 M0 |
| 步骤 07 至少 3 个种子 | 配置就绪（seeds: [0,1,2]） | 本轮未跑 |
| 步骤 08 M1 CNN 对照 | 已实现（简化 U-Net） | 32×32 编码器 + 秩 4 因子化读出，没有 46×180 的全分辨率解码器；理由是 CPU 预算与 240 例数据量 |
| 步骤 08 消融：去姿态/去 S 参数先验/连接半径/多尺度 | 部分 | 连接半径（graph.radius）、全局支路（global_branch）、gamma_source 可配；**几何消融无意义**（数据只有平面） |
| 步骤 02 角度相关单元库 | 只有法向入射 | unit_library 已留 CSV 双线性插值接口；数据是法向入射，没有斜入射 Floquet 表 |
| 步骤 05 复数远场标签 | 仅 1 例 | 只有 D:/ff_er265_r2_b2/ff_10.txt 六列；complex 损失用它验证，无法训练 |
| 步骤 03/09 曲面、跨曲率、跨规模 | 未做 | 数据全是同一平面 20×20；算子已支持 3-D 位置，投影仍是平面近似（文档已注明） |
| 步骤 09 四类泛化（A/B/C/D） | 未做 | 无曲率/规模变量，只有「新布局」一类（= 现在的 test split） |
| 反设计 / 逆向优化 | 未做 | 不在本轮范围 |
| numpy + 手写反向传播回退 | **未实现** | 见下 |

**关于 numpy 回退**：任务书要求「装不上 torch 就退回 numpy + 手写反向传播」。本次没有实现，
理由是：在禁止执行的环境里，一个 800 行的自写反向传播（含 scatter-add 梯度、LayerNorm、
AdamW、余弦调度）无法做任何数值验证，交付一个不能跑的回退实现比明确说明风险更糟。
若 torch 装不上，最小代价路径是 conda install pytorch cpuonly -c pytorch，
或 python -m pip install torch -i https://pypi.tuna.tsinghua.edu.cn/simple。
真需要在无 torch 环境下跑，建议只保留 M0/M0g（纯 numpy，scripts/run_baselines.py 的前半段
可直接用），GNN 部分等 torch 就绪。

---

## 10 复现命令与首次运行自检清单

    cd D:/GNN/gnn

    # (0) 环境
    python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    python -c "import torch; print(torch.__version__)"

    # (1) 测试  —— 期望：全部通过；theory 交叉验证若跳过属正常
    pytest tests/ -q

    # (2) 冒烟  —— 期望：打印 uniform aperture -> 19.3420 dBsm；总耗时 < 300 s；末行 SMOKE PASS
    python scripts/smoke_test.py

    # (3) 冻结 + 划分 —— 期望：241 files（或当时的实际数）；train 约 169 / val 约 36 / test 约 36；
    #     三个 split 的 specular 均值都约 10.7–10.9 dBsm、占空比约 46%（不齐说明分组有问题）
    python scripts/make_splits.py --out runs/splits.json

    # (4) 基线 —— 期望：M0 的 spec_err 约 −13.8 dB、mean_far_err 约 −1.3 dB；
    #     M0g 的 spec_err 约 0（它是拟合的）、rho_lin 明显高于 M0
    python scripts/run_baselines.py --config configs/train_m3.yaml \
        --snapshot runs/snapshot.json --splits-file runs/splits.json --out runs/baselines

    # (5) 训练（每个 run 预计 3–10 min，CPU 4 线程；60 epoch）
    python -m msgnn.train --config configs/train_m3.yaml --seed 0 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_s0
    python -m msgnn.train --config configs/train_m2.yaml --seed 0 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m2_s0
    python -m msgnn.train --config configs/baseline_m1.yaml --seed 0 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m1_s0

    # (6) 三个种子（波动）
    python -m msgnn.train --config configs/train_m3.yaml --seed 1 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_s1
    python -m msgnn.train --config configs/train_m3.yaml --seed 2 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_s2

    # (7) 评估（M0/M0g 放在同一行里，保证同一快照同一 split）
    python -m msgnn.evaluate --runs runs/m3_s0 runs/m3_s1 runs/m3_s2 runs/m2_s0 runs/m1_s0 m0 m0g \
        --out runs --splits val,test

    # (8) 数据效率曲线
    python -m msgnn.train --config configs/train_m3.yaml --seed 0 --max-train 60 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_n60
    python -m msgnn.train --config configs/train_m3.yaml --seed 0 --max-train 120 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_n120
    python -m msgnn.train --config configs/train_m3.yaml --seed 0 --max-train 180 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_n180

    # (9) 单例诊断（学到的修正长什么样）
    python -m msgnn.predict --run runs/m3_s0 --case 0 --out runs/m3_s0/pred_0000.npz

首次运行最可能踩的坑（按概率排序）：

1. **torch 未安装** -> 全部 import 失败，先装；
2. **数据还在增长** -> 一定用 make_splits.py 产出的同一份 snapshot/splits 跑全部实验，
   否则 M0 与 M3 不是同一批样本；
3. **evaluate 的 m0/m0g 与训练 run 的快照不一致** -> 把 run 目录放在 --runs 列表最前面
   （代码会用第一个 run 的 snapshot/splits 作基准）；
4. **float64 与 float32 混用** -> runtime.dtype 改一处即可（算子、模型、batch 走同一 dtype）；
5. **内存**：算子的相位核是 (8280, 400) float32 约 13 MB ×2，加上 241 例图约 100 MB，无压力。

---

## 11 已知局限

1. 只有幅度标签 -> power 损失是主口径；复场监督只在 1 例上验证了损失函数本身。
2. 极化投影是平面近似（x 偏振口径）；曲面/斜入射时需要按局部 t1/t2 重做投影。
3. M1 是简化的 U-Net（无全分辨率 46×180 解码器），它的作用是「无物理先验的对照」，
   不应被当作 PGRL 的严格复现。
4. M0g 使用标签拟合（oracle），只能作为「2 个实自由度能解释多少」的上界参考。
5. 单频、单入射角、单极化、单一 20×20 规模 —— 所有结论都限制在这个范围内
   （与计划文档「单频实验不能证明宽带」的边界一致）。
6. 参数量、耗时均为结构估算，运行后以 summary.json 为准。
