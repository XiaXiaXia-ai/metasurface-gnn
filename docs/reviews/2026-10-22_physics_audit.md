# 物理背景、数据形式与曲面预留审计（只读）

- 对象：`D:/GNN/gnn/msgnn` 全包、`gnn/tests`、`gnn/configs`、`gnn/scripts`、`gnn/README.md`、`gnn/REPORT.md`、`docs/gnn_architecture.md`、`docs/CONVENTIONS.md`
- 方式：**只读静态审查**。本次未运行 python / pytest / 训练，未修改任何源文件；唯一写入是本报告。
- 证据标记：
  - 普通 `file:line`：本次逐行阅读的代码/文档/数据；
  - **[既有实测]**：来自 `gnn/runs/verify/REPORT_verify.md` 的 2026-10-22 08:5x 记录，**不是本次执行**；
  - **未能确认**：需要运行或需要 CST 原始设置才能判定，本报告不猜。
- 数据现场只读核对：`D:/dataset/results/ff` 与 `results` 各有 **266** 个文件；`ff_0000.txt` 8280 行 4 列；`ff_10.txt` 65160 行 6 列；冻结快照 247 例、247 组。详见附录 A。

---

## 0 结论摘要

| 问题 | 一句话结论 |
|---|---|
| **Q1 物理是否符合** | **数值链路基本自洽，物理契约不完整**：q=Γ 的无量纲口径、19.342 dBsm 全 1 自检、矢量投影、绝对 dBsm 标签都在代码里；但 q 只被实现为“每节点 1 个复反射系数”，没有计划要求的等效源基函数（方向/面积/单位/K），背景项 b 与 mean(Δq) 不可辨识，相位原点与复场约定未写明。按当前“平面/单频/法向/幅度-only”任务可运行，按计划步骤 04 的验收口径只能算**部分符合**。 |
| **Q2 与现有数据形式是否匹配** | **4 列幅度 + power 损失自洽，8280 点网格与 CST 导出对得上**；但 complex 模式是**可配置却不可运行的空壳**（仅 1 例、1° 网格未接、train 会崩），切分在“每例独立随机码”下**退化为逐样本随机切分**（`n_cases=247=n_groups`），且 `rho_lin` 的 −60 dB 截断与 θ=90 包含会改变头条指标。 |
| **Q3 曲面预留是否足够** | **不够**：3D 位置只是“z=0 的占位”，局部 t1/t2/n、面积、法向、3D 边特征、(u,v) 参数化构图、curvature/radius/frame 字段、遮挡/背照标记全部缺失或仅占位；辐射算子接受 3D 位置与 3D 观测方向，但源方向仍是全局 x̂，不是任意姿态。最小路径是“geometry provider + 逐节点矢量源 + 观测掩码”三件套。 |
| **总体判断** | 作为第一阶段（平面、10 GHz、法向、x 极化、幅度标签）的**物理自检与数据管线是可信的**（19.342 自检、torch↔numpy、4 列解析均有代码/既有实测支撑）；作为“曲面 + 复数远场”的后续基座，**物理定义和几何接口都还差一层**，现在直接扩曲面会把“模型误差”与“表示/坐标误差”混在一起。 |

---

## 1 结论摘要（逐项证据）

### 1.1 Q1：物理是否符合

| # | 检查项 | 结论 | 关键证据 |
|---|---|---|---|
| 1 | q 的物理定义与单位 | **部分**。q 被定义为“复反射系数”，无量纲；q=1（全 1 口径）严格给出 PEC 平板 19.342 dBsm，绝对尺度是钉住的。但代码没有写出“q 是哪种等效源基函数的系数”，也没有逐节点面积/方向/源类型，K 硬编码为 1。 | `gnn/msgnn/physics/unit_library.py:1-10`；`gnn/msgnn/physics/baseline.py:29-31`；`gnn/msgnn/physics/radiation.py:44-46,146-148`；`docs/gnn_architecture.md:17`；计划 `_tmp_spec/spec1.md:58,124` |
| 2 | S11 是否被误当源系数/电流 | **基本符合，但映射未写明**。q 就是 Γ，没有被当作有量纲电流；对反射阵的 PO 口径，ΣΓ 作为孔径加权是标准做法，|Γ|² 的 −1.24 dB 也被文档识别为数值损耗。缺口在于：从 Γ 到“源系数”的映射是恒等映射，没有 (1+Γ)、没有源基函数说明。 | `gnn/msgnn/physics/unit_library.py:5-10,16-21`；`gnn/msgnn/physics/baseline.py:29-31`；`gnn/msgnn/physics/radiation.py:146-148`；计划 `_tmp_spec/spec1.md:58` |
| 3 | 矢量投影是否真的用于 Eθ/Eφ | **部分**。前向算子确实用 `pθ=cosθcosφ, pφ=−sinφ`，默认 vector；但训练损失与指标只用总 σ，Eθ/Eφ 只作为中间量，没有单独监督，也没有 E/H 面指标。也就是说，**投影用在了前向，没有用在验收**。 | `gnn/msgnn/physics/radiation.py:16-24,72-80`；`gnn/msgnn/config.py:56`；`gnn/configs/train_m3.yaml:16`；`gnn/tests/test_radiation.py:66-76`；`gnn/msgnn/data/dataset.py:299-308`；`gnn/msgnn/data/build_graph.py:143-145` |
| 4 | 绝对电平标定（全 1 → 19.342 dBsm） | **符合**。解析值 `4πA²/λ²` 与 `const_c·N` 一致；代码断言两种投影在 θ=0 都给 19.342；既有实测 19.342005835。数据侧 `ff_0000` 的 θ=0 总 σ=10.798 dBsm 与 `res_0000` 的 `specular_dbsm=10.798` 逐位吻合，说明 dBsm 参考面一致。 | `gnn/msgnn/physics/radiation.py:44-53,257-266`；`gnn/tests/test_radiation.py:22-46`；`gnn/REPORT.md:83-99`；**[既有实测]** `gnn/runs/verify/REPORT_verify.md:30-34`；`D:/dataset/results/ff/ff_0000.txt:1`；`D:/dataset/results/res_0000.json:1`；`theory/REPORT.md:460` |
| 5 | 地板/基板是否被重复计入 | **部分**。q0=Γ 来自孤立单元 Floquet，已经把 PEC 地板/基板包含在反射系数里；代码没有再单独加“地板/基板项”，所以没有显式重复计算。但背景项 b 是**无约束的均匀复偏移**，代码没有定义它与 q0 的分工，也没有禁止 b 去吸收地板/基板或全局幅度误差；再加上 b 与 mean(Δq) 简并（见 B3），“分工”只停留在文字上。 | `gnn/msgnn/physics/unit_library.py:1-10`；`gnn/msgnn/models/residual_gnn.py:8-14`；`gnn/msgnn/models/pipeline.py:53-60`；计划 `_tmp_spec/spec1.md:62` |
| 6 | 复场相位约定（exp(+jωt)、外相波） | **部分 / 未能确认**。算子的核是 `exp(+j k r·s)`；在 exp(+jωt) 下，外向波在观察点的**相对**相位确实是 `exp(+j k ŝ·r_n)`（绝对因子 `exp(−jkR)` 是公共相位），所以前向的相对相位并不矛盾。但代码从未写明这一约定，也没有保留绝对相位 `exp(−jkR)`；`load_complex_case` 直接读 CST 相位，没有共轭/全局相位对齐。CST 导出的时间约定**未能确认**。 | `gnn/msgnn/physics/radiation.py:4-10,179`；`gnn/msgnn/data/dataset.py:311-320`；`gnn/msgnn/losses.py:100-115`；计划 `_tmp_spec/spec1.md:69,125`；`theory/common.py:8`；`D:/ff_er265_r2_b2/ff_10.txt:1` |
| 7 | 单元库是否只有法向两态，代码是否悄悄假设别的 | **符合当前数据；扩展位未接线**。库只有 0/1 两态、法向、10 GHz，与数据一致；代码没有偷偷假设斜入射，而是**在需要角度时直接忽略角度**：`build_graph` 和 `baseline_fields` 调用库时都不传 θ/φ，`unit_table` 从未被 `build_context` 加载，`return_oob` 也从未在管线里使用。对平面法向数据没问题；对曲面，局部入射角变化会被静默地按法向处理。 | `gnn/msgnn/physics/unit_library.py:5-9,23-30,101-113,136-137`；`gnn/msgnn/data/build_graph.py:109`；`gnn/msgnn/physics/baseline.py:38`；`gnn/msgnn/config.py:58`；`gnn/msgnn/experiment.py:138` |

### 1.2 Q2：与现有数据形式是否匹配

| # | 检查项 | 结论 | 关键证据 |
|---|---|---|---|
| 1 | 4 列幅度标签 + power 损失是否自洽 | **自洽**。两列是每个极化分量的 dBsm（`20log10|E|`），代码反解 |Eθ|、|Eφ| 后求 `σ=|Eθ|²+|Eφ|²`，再在 dB 域用 asinh 压缩的 power 损失；没有逐样本峰值归一化。 | `gnn/msgnn/data/dataset.py:6-10,299-308`；`D:/dataset/results/ff/ff_0000.txt:1`；`gnn/msgnn/losses.py:50-88`；`gnn/configs/train_m3.yaml:27`；`gnn/REPORT.md:80` |
| 2 | 8280 点网格与 θ 范围是否与 CST 导出一致 | **一致**。46×180=8280，θ 0–90 步 2°，φ 0–358 步 2°，theta 外层；`_ff_is_valid` 逐点比对角度；现场 `ff_0000` 首行 θ=0 φ=0、末行 θ=90 φ=358。 | `gnn/msgnn/data/dataset.py:69-73,202-213`；`gnn/tests/test_dataset.py:21-29`；`D:/dataset/results/ff/ff_0000.txt:1,8280` |
| 3 | complex 模式只有一个样本会不会被误用 | **会被误用；实际是阻断（complex 分支）**。`loss.mode` 允许 `complex`，但 `ComplexLoss` 要 dict 输入，`train.py` 传的是 `sig_db` 张量；没有 complex DataLoader；唯一 6 列文件是 1°/0–180，和 2° 训练网格不一致；也没有全局相位对齐。 | `gnn/msgnn/config.py:285-286`；`gnn/msgnn/losses.py:100-115`；`gnn/msgnn/train.py:109`；`gnn/msgnn/data/dataset.py:311-320`；`gnn/tests/test_dataset.py:86-104`；`D:/ff_er265_r2_b2/ff_10.txt:1,65160` |
| 4 | 快照/切分在“每例独立随机码”下是否退化成逐样本随机切分（泄漏风险） | **退化了，但不是同例角度泄漏**。`layout_id` 由 code 的 sha1 得到，247 例 → 247 组，分组切分等价于逐样本随机切分；同一 case 的所有角度仍在同一 split，所以没有“同阵列角度点泄漏”。真正的问题是测试集与训练集 i.i.d.，不能支撑“新布局泛化”的结论；近似重复码也没有去重。 | `gnn/msgnn/data/dataset.py:30-33,189,324-370`；`gnn/runs/verify/ctx/splits.json:5-6`（`n_cases=247, n_groups=247`）；**[既有实测]** `gnn/runs/verify/REPORT_verify.md:154-155`；`_tmp_spec/spec2.md:113` |
| 5 | 缺相位的事实是否被代码掩盖 | **文档没有掩盖，但 complex 路径是空壳**。`load_target` 只返回幅度/总 σ，没有伪造相位；README/REPORT 反复写明“只有幅度”。可是 `predict.py` 会输出复数 Eθ/Eφ，`ComplexLoss` 也存在，容易让人以为复场监督已经可用；实际没有数据管线。 | `gnn/msgnn/data/dataset.py:299-308`；`gnn/README.md:75-78`；`gnn/REPORT.md:316,398`；`gnn/msgnn/predict.py:49-56`；`gnn/msgnn/losses.py:91-119` |
| 6 | 指标口径是否与数据/理论一致 | **部分**。`rho_lin` 先把 pred/targ 截到 −60 dB 再算线性功率 Pearson，且包含 θ=90；`rho_db` 用 6–90，而 theory 的标准口径是 6–60（θ=90 处标量投影退化）。这会改变头条指标，尤其 scalar 模式。 | `gnn/msgnn/evaluate.py:57-58,71-82`；`gnn/msgnn/config.py:113`；`theory/REPORT.md:283,331`；**[既有实测]** `gnn/runs/verify/REPORT_verify.md:175-182` |

### 1.3 Q3：曲面预留是否足够

**总体：不够。** 逐项见第 3 节矩阵。最关键的三条：

1. **只有 3D 位置的占位，没有局部坐标系/面积/法向**：图节点位置是 `[x, y, 0]`，节点特征只有 x/λ、y/λ，法向只有标量 `normal_z`（恒 1）；辐射常数用全局 `P²`，没有逐节点面积。
2. **辐射算子只接受“全局 x̂ 极化的标量源”**：位置和观测方向可以是 3D，但每个节点的源方向没有进入算子；`projection_factors` 仍是全局 `cosθcosφ / −sinφ`。文档 `radiation.py:26-28` 写“curved arrays work unchanged”，这是**过度声明**。
3. **图与数据契约没有几何入口**：`lattice_xy` + `edge_index_grid` 只生成平面方阵；边特征用 `pos_xy`；config/Case 没有 curvature/radius/frame；没有遮挡/背照标记；指标没有任意观测域掩码。

---

## 2 问题清单

### 2.1 阻断

> 说明：当前默认路径是 `model=m3, loss.mode=power, 平面 20×20`；以下 B1 只阻断 complex 分支，B2/B3 阻断“按计划步骤 04/归因结论”的验收，不阻断现有平面幅度路径的启动。

#### B1｜`loss.mode=complex` 可配置但不可运行，6 列样本也接不进训练

- **file:line**：`gnn/msgnn/config.py:285-286`；`gnn/msgnn/losses.py:100-115`；`gnn/msgnn/train.py:109`；`gnn/msgnn/data/dataset.py:311-320`；`gnn/tests/test_dataset.py:86-104`
- **问题**：`build_loss` 会返回 `ComplexLoss`，但它的 `forward` 读取 `pred["eth_re"]` 等 dict 键；`train.py` 传的是 `out["sig_db"]` 与 `batch["sig_db"]` 两个张量，因而一旦把 `loss.mode` 设为 `complex`，第一个 batch 就会报 `TypeError`/`IndexError`。同时，唯一的 6 列文件是 1°、θ 0–180，训练 `Grid` 是 2°、θ 0–90；`load_complex_case` 只被测试调用，没有 Dataset/collate 路径；也没有全局相位对齐。
- **依据**：用户 §2“全库只有一个含相位的样本”；计划 `_tmp_spec/spec1.md:78` 要求标签 `[M,4]`（ReFθ/ImFθ/ReFφ/ImFφ）；`_tmp_spec/spec2.md:193-194` 的复场损失。
- **最小修法**：
  1. 短期：在 `config._validate` 里对 `loss.mode=="complex"` 直接抛 `ConfigError`，并在 README 标注“未实现”，避免用户按文档踩坑；
  2. 真正实现：加 `ComplexCase`/`ComplexGraphDataset`（1° 网格或重采样到 2°），`collate` 产出 `eth_re/eth_im/eph_re/eph_im`，`PhysicsPipeline.forward(return_fields=True)` 的字段直接作为 pred，`train` 分支调用 `crit(pred_dict, targ_dict)`；
  3. 相位：加一个全局相位/共轭选项，先在 `ff_10.txt` 上最小化相位残差，再允许训练。

#### B2｜q 只有“每节点 1 个复反射系数”，没有计划要求的等效源基函数（方向、面积、单位、K）

- **file:line**：`gnn/msgnn/physics/unit_library.py:5-10,38-39`；`gnn/msgnn/physics/baseline.py:29-31`；`gnn/msgnn/physics/radiation.py:44-46,146-148`；`gnn/msgnn/data/build_graph.py:109`；计划 `_tmp_spec/spec1.md:58,124`
- **问题**：q 被实现为 `q_n = Γ_bit(n)`，每节点一个复数，直接进入标量孔径求和。代码没有说明：
  - 这是电/磁偶极子还是等效面元；
  - 源的方向（全局 x̂ 还是局部 t1/t2 的哪一维）；
  - 每个源代表的面积（`const_c` 用全局 `P²`，不是 `area_n`）；
  - 单位（q 无量纲；输出 σ 为 m²；中间没有 A·m 或 V）；
  - 每节点 K 个复系数的 K（现在硬编码 1）。
  对当前“平面、法向、x 极化、同极化标量单元”任务，恒等映射 Γ→q 与“归一化 x̂ 点源”在数值上等价，19.342 自检也钉住了尺度；但它**不满足计划步骤 04 的“先固定 q 定义”验收**，也无法表达曲面上的局部源方向。
- **依据**：用户 §1“不能把无量纲 S11 直接当作电流或源系数；q 的定义必须写清”；计划 `_tmp_spec/spec1.md:58`（“q 定义为选定局部等效源基函数的复系数……不能把无量纲 S11 直接当作电流”）、`:124`（“说明电/磁源、方向、单位、面积及角向辐射因子”）。
- **最小修法**：
  1. 在文档和 `UnitLibrary`/`radiation` 的 docstring 里明确写：`q_n` 是“归一化到 |q|=1 即 PEC 平板的 x̂ 电偶极子等效源系数”，并给出 Γ→q 的恒等映射及其适用条件（法向、同极化、单元尺度远小于 λ）；
  2. 把 `const_c` 改为逐节点 `C_n = 2√π/λ · area_n · 1e-3`，`area_n` 从几何提供者传入；
  3. 若要扩曲面，把标量 q 升级为每节点源矢量（或 2×2 极化率），至少支持局部 `t1/t2` 两个方向；先用一个倾斜单源/双源解析测试验证方向与极化。

#### B3｜M3 的 b 与 mean(Δq) 简并，“|b|≈0.37”的归因和验收不可辨识

- **file:line**：`gnn/msgnn/models/pipeline.py:53-60`；`gnn/msgnn/models/residual_gnn.py:51-60,84-86`；`gnn/REPORT.md:256,273`
- **问题**：`q = q0 + Δq + b`，其中 `b` 是每样本一个复数并广播到所有节点，`Δq` 是逐节点自由输出；对任意常数 c，`(Δq + c, b − c)` 给出完全相同的 q。因此：
  - `|b|` 不是唯一可解释的“共同模幅度”；训练可以把均匀分量放到 `Δq` 的均值里，也可以放到 `b` 里；
  - REPORT 的验收判据“M3 的 |b| 落在 0.25–0.55”与“mean(Δq) ≈ b ≈ 0.37”在数学上会**重复计数**（两者都 0.37 意味着总均匀分量约 0.74）；
  - 代码没有任何 centering、正交化或惩罚来防止这一点。
- **依据**：线性代数上的不可辨识性；`gnn/REPORT.md:130-133` 对 b 的定义、`:256` 的验收、`:273` 的预期；计划 `_tmp_spec/spec1.md:174` 只禁止对 |Γ| 强加 ≤1，并未提供 b/Δq 的分离约束。
- **最小修法**：
  1. 在 `GraphNet.forward` 里对每张图的 `Δq` 做 centering（减去该图节点均值），把均值并入 `b`；这样 `b` 是唯一的均匀分量，`mean(Δq)=0` 成为可检验约束；
  2. 或者删掉 `b`，直接用 `mean(Δq)` 作为共同模，REPORT 改报 `mean(Δq)`；
  3. 加一个诊断/测试：未训练 M3 与 M0 逐点相同；训练后打印 `mean(Δq)`、`std(Δq)`、`|b|` 和 `corr(b, code)`，并重新推导 0.37 的对照。

### 2.2 重要

#### M1｜相位约定与绝对相位原点未写明，复场标签无法直接比较

- **file:line**：`gnn/msgnn/physics/radiation.py:4-10,179`；`gnn/msgnn/data/dataset.py:311-320`；`gnn/msgnn/losses.py:100-115`；计划 `_tmp_spec/spec1.md:69`
- **问题**：代码写 `exp(+j k r·s)`，在 exp(+jωt) 下这是外向波的**相对**相位（绝对 `exp(−jkR)` 被省略），本身不矛盾；但文档从未说明时间约定，也没有定义远场相位原点、S11 参考面与入射相位。`load_complex_case` 直接把 CST 的相位（`ff_10.txt` θ=0 的 Eθ 相位 55.56°）转成复数，没有共轭/全局相位对齐；ComplexLoss 也没有可学习的全局相位。CST 的时间约定**未能确认**。
- **依据**：计划 `spec1.md:69`“代码采用 exp(+jωt)；外向波 exp(−jkr)……核对 CST 导出约定，必要时统一转换”；`:125`“观察方向的平移相位为 exp(+jk·ŝ·r_i)”；用户 §1 要求核对“exp(+jωt)、外相波”。
- **最小修法**：在 `radiation.py` 顶部写清“exp(+jωt)、相对相位 +jk ŝ·r、绝对相位省略”；加 `phase_convention`/`conjugate` 选项；在 6 列样本上分别用 `+j` 与 `−j` 拟合一个全局相位，报告相位残差；在 complex 训练前把全局相位作为标定步骤。

#### M2｜单元库只有法向两态，角度扩展是死代码，越界标记从未使用

- **file:line**：`gnn/msgnn/physics/unit_library.py:23-30,101-113,136-137`；`gnn/msgnn/data/build_graph.py:109`；`gnn/msgnn/physics/baseline.py:38`；`gnn/msgnn/config.py:58`；`gnn/msgnn/experiment.py:138`
- **问题**：`UnitLibrary.from_csv` 和 `return_oob` 写好了，但 `build_context` 永远用 `UnitLibrary.floquet`，`build_graph`/`baseline_fields` 不传 θ/φ，`unit_table` 配置从未被读取。对平面法向数据这是正确的；对曲面，局部入射角会变化，代码会**静默地**用 0° 的 Γ，且不会记录越界。
- **依据**：计划 `spec1.md:154`“对越界角度、遮挡与背照单独标记，禁止悄悄截断角度”；用户 §1 第 4 条“平面单元库映射到曲面依赖局部平面近似”。
- **最小修法**：从几何提供者取每节点 `θ_loc, φ_loc`，传给 `library(...)`；若 `table is None` 且存在 `|θ_loc|>tol`，直接 raise 或写 warning；把 `return_oob` 的布尔值存进 graph 的 `library_flags`；在 `build_context` 里按 `cfg.physics.unit_table` 加载 CSV。

#### M3｜单元库没有材料/几何/端口/模式元数据，Γ 是硬编码的两个数

- **file:line**：`gnn/msgnn/physics/unit_library.py:38-39,59-68`；`gnn/msgnn/config.py:59`；`gnn/README.md:80-81`；计划 `_tmp_spec/spec1.md:103-105`
- **问题**：`UnitLibrary` 只有 `gamma/freq_ghz/theta_ax/phi_ax/table/source`；εr=2.65、tanδ=0.0013、h=1.5 mm、P=14 mm、r=4.7/2.0 mm、Floquet 模式、TE/TM、参考面、归一化都没有进入数据结构。`patch_r_mm` 配置存在但从未被读取。数值本身符合用户给的 Γ0/Γ1，但不可追溯。
- **依据**：计划步骤 02 要求 `unit_library.h5` 带 geometry/theta/phi/R/模式/参考面与 `unit_metadata.json`；用户 §1 给出了完整的单元参数。
- **最小修法**：加 `UnitMeta` dataclass（εr、tanδ、h、P、r0/r1、freq、port reference、Floquet mode、polarization），从 JSON 读取并写进 run 的 `config.yaml`/summary；加一个 schema 测试。

#### M4｜4 列校验写成 `>=4`，6 列文件会被静默当成幅度读

- **file:line**：`gnn/msgnn/data/dataset.py:207-213`；`gnn/msgnn/data/dataset.py:304-306`；`cst/export_farfield.py:16-17`；`gnn/msgnn/data/dataset.py:311-320`
- **问题**：`_ff_is_valid` 只要求 `d.shape[1] >= 4`。如果以后把 6 列（θ φ |Eθ|dB phase |Eφ|dB phase）导出放进 `results/ff`，它会通过校验，`load_target` 会把第 3 列（|Eθ|dB）和第 4 列（相位）当成两个幅度，得到完全错误的总 σ，且不会报错。
- **依据**：`cst/export_farfield.py:16-17` 明确 6 列格式；当前 4 列路径 `dataset.py:304-306`。
- **最小修法**：幅度路径要求 `d.shape[1] == 4`；检测到 6 列时走 complex 解析或明确报错“请放到 complex 目录”；加一个 4/6 列 fixture 测试。

#### M5｜快照存了 sha256，但加载时只校验 size

- **file:line**：`gnn/msgnn/data/dataset.py:274-276`（写 sha256）；`gnn/msgnn/data/dataset.py:250-256`（只比 size）；`docs/gnn_architecture.md:79`
- **问题**：`scan_cases` 只检查 `os.path.getsize`，不校验 `sha256`。同尺寸内容变化（例如重跑覆盖、后处理改列）不会触发失败，和文档宣称的“sha256 冻结”不一致。
- **依据**：计划 `spec1.md:145`“划分无基础布局泄漏……绝对幅值未被逐样本峰值归一化丢失”；架构文档 `docs/gnn_architecture.md:77-81` 的防泄漏三件套。
- **最小修法**：在 `scan_cases` 加载快照时逐文件校验 sha256（或至少 mtime+size+hash 三选二）；不一致直接 raise；加一个“改一个字节”测试。

#### M6｜切分在当前数据上退化为逐样本随机切分，不构成“新布局”泛化

- **file:line**：`gnn/msgnn/data/dataset.py:30-33,189,324-370`；`gnn/runs/verify/ctx/splits.json:5-6`；**[既有实测]** `gnn/runs/verify/REPORT_verify.md:154-155`
- **问题**：`layout_id = rec.get("layout_id") or "L"+sha1(code)[:12]`；当前 `res_*.json` 没有 `layout_id`，每例 code 独立随机 → 247 例 247 组。分组切分与逐样本随机切分完全等价。没有同例角度泄漏（同一 case 的所有角度点仍在同一 split），但测试集是 i.i.d. 同分布样本；REPORT/README 中“新布局泛化”的措辞缺乏数据支撑。近似重复码（Hamming 距离很小）也没有去重。另外 `load_or_make_splits` 只做 `sp[k] = [i for i in sp[k] if i in have]`，**不在 splits 里的 case 会被静默丢掉**，没有“splits 覆盖全部 cases”的校验（`gnn/msgnn/data/dataset.py:387-394`）。
- **依据**：`_tmp_spec/spec2.md:113`“按阵列布局划分，不能把同一阵列的不同角度点随机拆到训练/测试”；`gnn/runs/verify/ctx/splits.json:5-6` 的 `n_cases=247, n_groups=247`。
- **最小修法**：短期在 summary 里同时打印 `n_cases/n_groups`，当两者相等时明确标注“i.i.d. 随机切分，不是组泛化”；中期生成“同物理布局、不同 code/seed/曲率”的 layout family，或使用 v2 的 `layout_id`；加近似重复码检测。

#### M7｜`rho_lin` 先截到 −60 dB 再算线性相关，且包含 θ=90，头条指标被改变

- **file:line**：`gnn/msgnn/evaluate.py:57-58`（截断）；`gnn/msgnn/evaluate.py:71-72`（`front = th <= 90`）；`gnn/msgnn/evaluate.py:74-82`；`gnn/msgnn/config.py:113`；`theory/REPORT.md:283,331`
- **问题**：`p = max(pred, −60)`、`t = max(targ, −60)` 之后才做 `10**(p/10)`，深零陷被抬到 −60，线性功率的方差被改写；θ=90 又包含在 `rho_lin` 与 6–90 的 RMSE 里（theory 的标准口径排除 θ=90）。既有实测显示 scalar 在 6–90 的 RMSE 从 3.2 涨到 37 dB，说明这个口径对结论影响很大。此外 `PhysicsPipeline.forward` 用 `sigma_db(fields, db_floor=-60)` 把**预测本身**也截到 −60（`gnn/msgnn/models/pipeline.py:82,89`），深零陷没有梯度，模型学不到 −60 以下的结构。
- **依据**：`theory/REPORT.md:283`“θ=90 的环污染 ρ”；`:331`“θ∈[0,90)，θ=90 剔除”；**[既有实测]** `gnn/runs/verify/REPORT_verify.md:175-182`。
- **最小修法**：`rho_lin` 用未截断的线性 σ（分母加 `1e-300`），−60 floor 只用于 dB 域的 RMSE/bias；默认排除 θ=90；同时给 6–60（theory 口径）和 6–90 两行。

#### M8｜4 列数据有 |Eθ|、|Eφ| 两列，但训练/指标只看总 σ，E/H 证据没有被验收

- **file:line**：`gnn/msgnn/data/dataset.py:304-308`（返回 eth_mag/eph_mag）；`gnn/msgnn/data/build_graph.py:143-145`（只存 sig_db）；`gnn/msgnn/evaluate.py:60-91`（总 σ）；`theory/REPORT.md:326`
- **问题**：矢量投影之所以是默认，是因为实测 E/H 面差 −1.84 dB、矢量预测 −1.61 dB；但代码在 `load_target` 之后只保留总 σ，两列幅度信息被丢掉。损失和指标都不区分 E/H，模型可以总 σ 拟合得不错而 Eθ/Eφ 分配错误，上述物理证据没有被用作验收。
- **依据**：用户 §1“实测 E/H 面差 −1.84 dB……辐射层必须用矢量投影”；`theory/REPORT.md:326`。
- **最小修法**：在 `GraphDataset` 保留 `eth_mag/eph_mag`（或复场），`metrics_for_sample` 增加 E 面（φ=0）/H 面（φ=90）的 6–60 band 均值与差；加一个可选的 per-component power loss（权重默认 0）。

#### M9｜complex 损失的逐方向归一化会抹掉绝对电平（未来实现时）

- **file:line**：`gnn/msgnn/losses.py:110-115`；`gnn/msgnn/config.py:88`；计划 `_tmp_spec/spec1.md:80`；`_tmp_spec/spec2.md:194`
- **问题**：`a2 = (w*tr).sum(dim=1)/w.sum()`，`e_m = tr + eps_rel*a2`，再 `sum(w*num/e_m)/sum(w)`。这是**逐方向**相对误差，均匀 3 dB 偏低与形状正确在损失上几乎等价；而计划的主损失是 `sum w|ΔF|² / (sum w|F|² + eps)` 的全局分母，保留绝对电平敏感性。代码的 `complex_compress=False` 才接近计划形式。
- **依据**：用户 §1“远场标签必须是复数、绝对尺度”；计划 `spec1.md:80`“按固定入射幅度或训练集统一尺度归一化，保留绝对散射强度”。
- **最小修法**：complex 模式默认 `complex_compress=False`（或同时报告两种）；加一个“整体 3 dB 偏低”的单元测试，要求 loss 明显大于正确预测；在 REPORT 里明确 complex 模式的绝对电平口径。

#### M10｜M2 vs M3 的消融混淆了 q0、全局支路和零初始化

- **file:line**：`gnn/configs/train_m2.yaml:17-22`；`gnn/msgnn/models/pipeline.py:47-60`；`gnn/msgnn/models/residual_gnn.py:33-35,54-60`；`gnn/REPORT.md:121-122,131-133`
- **问题**：M2 = 无 q0、`global_branch=false`、无零初始化；M3 = q0 + Δq + b、有全局支路、零初始化。REPORT 把 M3−M2 解释为“残差形式的价值”，但这同时改变了输入先验、输出参数化和初始化，不能归因到单一模块。计划明确警告过这一点。
- **依据**：`_tmp_spec/spec1.md:180`“不要把同时改变网络、输入和损失的对比解释为某个单一模块的因果证据”；`:181-182` 的消融要求。
- **最小修法**：增加两个控制：M3-noglob（`global_branch:false`，其余同 M3）和 M2+q0（`direct:false` 的残差形式、无全局支路），至少把 M3−M2 拆成“q0 的作用”和“全局支路的作用”；REPORT 改写结论措辞。

#### M11｜`max_cases` 截断用硬编码 0.7/0.15/0.15，可能留下空 split

- **file:line**：`gnn/msgnn/experiment.py:125-133`
- **问题**：`n_tr=round(0.7*k)`、`n_va=round(0.15*k)`、`n_te=k-n_tr-n_va`，与 `cfg.data.val_frac/test_frac` 无关；当 k 很小时（smoke 的 8 例）会得到 1/1/6 等分布，甚至可能让 train/val 为空；而 `splits` 文件仍保存全量，后续 evaluate 会看到不同的集合。
- **依据**：计划 `spec1.md:146`“正式数量和比例应按实际覆盖与算力调整”；代码自己声明 `max_cases` 只是“评估子集”（`experiment.py:126-127`）。
- **最小修法**：用 `cfg.data.val_frac/test_frac` 计算；对空 split 直接报错；把实际使用的 `cases` 列表写进 run 的 summary，避免 evaluate 与 train 看到的集合不一致。

#### M12｜`Grid.from_step` 硬编码 2°/0–90，快照的 n_theta/n_phi 只用了 step

- **file:line**：`gnn/msgnn/data/dataset.py:69-73`；`gnn/msgnn/experiment.py:112`；`gnn/msgnn/evaluate.py:236-242`；`gnn/runs/verify/ctx/snapshot.json:6-8`
- **问题**：`Grid.from_step(step)` 固定 θ 0–90、φ 0–358；快照虽然记录了 `n_theta/n_phi`，加载时只取 `step`。1° 的 6 列文件、未来 0–180 的曲面背照数据、或不同 θ_max 的导出都会被截断/判为非法。`_grid_of` 也只从 step 重建。
- **依据**：用户 §2 的 2° 数据；`D:/ff_er265_r2_b2/ff_10.txt:1,65160` 是 1°/0–180。
- **最小修法**：快照保存 θ/φ 轴数组（或 θ_min/max、φ_min/max、step），`Grid` 从快照重建并校验 `n_theta*n_phi`；对 0–180 的支持与 `front_only` 分开。

#### M13｜`test_config_roundtrip` 静态推演会失败：嵌套 tuple 没有递归校验

- **file:line**：`gnn/msgnn/config.py:197-199`；`gnn/tests/test_dataset.py:122-130`
- **问题**：`EvalCfg.bands` 的类型是 `Tuple[Tuple[float,float], ...]`；`_check_container` 的 Ellipsis 分支对每个元素只调用 `_check_scalar`，而 `_check_scalar` 对 `Tuple[float,float]` 原样返回 list。于是重新加载后 `bands` 是“tuple of list”，原配置是“tuple of tuple”，`to_dict()` 不相等，`test_config_roundtrip` 会失败。这是本次静态推演，未执行确认。
- **依据**：`config.py` 文档承诺 YAML 往返；`tests/test_dataset.py:122-130` 的断言。
- **最小修法**：在 Ellipsis 分支里对 `get_origin(args[0]) in (tuple, Tuple)` 的元素递归调用 `_check_container`；加一个 `bands` 类型的显式测试。

### 2.3 建议

#### S1｜补“未训练 M3 == M0”和 b/Δq 分离的测试
- **file:line**：`gnn/msgnn/models/residual_gnn.py:54-60`；`gnn/msgnn/models/pipeline.py:53-60`
- **问题**：零初始化只在代码里，没有测试；B3 的 centering 也没有约束。
- **最小修法**：构造一个未训练 M3 与 M0 的 batch，断言 `sig_db` 逐点相等（float64）；训练后断言 `abs(mean(Δq)) < 1e-6`（若采用 centering）。

#### S2｜README 的 `mainlobe_boost` 默认值与 dataclass 不一致
- **file:line**：`gnn/README.md:96`（说默认 3.0）；`gnn/msgnn/config.py:84`（dataclass 默认 1.0）；`gnn/configs/train_m3.yaml:33`（3.0）
- **问题**：README 把“shipped config 的值”写成“默认值”；直接 `load_config(None)` 得到的是 1.0。架构文档 `docs/gnn_architecture.md:58-60` 也按 3.0 描述。
- **最小修法**：统一写成“dataclass 默认 1.0；三份 config 显式设 3.0”，或把 dataclass 默认改成 3.0（并同步测试）。

#### S3｜`runs/verify/` 是一份完整 shadow 包，应从交付树清理或明确标注为审计产物
- **file:line**：`gnn/runs/verify/shadow/msgnn/...`；`gnn/runs/verify/REPORT_verify.md:217-229`
- **问题**：它包含一份旧的 `msgnn` 副本和旧测试，容易与主包混淆，也会让“改动范围”审计变难。
- **最小修法**：移到 `docs/reviews/artifacts/` 或删除；若保留，在 README 里标注“一次性审计副本，不参与导入/测试”。

#### S4｜`KMP_DUPLICATE_LIB_OK=TRUE` 在包导入时修改全局环境
- **file:line**：`gnn/msgnn/__init__.py:14-21`
- **问题**：这是绕过 OpenMP 冲突的应急开关，可能掩盖真正的线程/内存错误；作为库的副作用不够干净。
- **最小修法**：移到启动脚本/文档，或在 `__init__` 里只设一次并打印 warning；CI 里显式设置。

#### S5｜`complex_ff` 默认指向仓库外的绝对路径
- **file:line**：`gnn/msgnn/config.py:39`；`gnn/msgnn/config.py:346-349`；`gnn/tests/test_dataset.py:89-91`
- **问题**：默认值 `D:/ff_er265_r2_b2/ff_10.txt` 是作者机器上的路径；换机后只有测试会 skip，用户可能不知道 complex 数据缺失。
- **最小修法**：默认 `None`，由 CLI/配置显式给出；在 README 的数据契约里写清。

#### S6｜`scan_cases` 只打印前 3 条 warning，坏文件/缺 json 可能被忽略
- **file:line**：`gnn/msgnn/data/dataset.py:236-244,258-260`
- **问题**：缺 `res_*.json` 的文件被 `continue` 跳过，不进入 warning；`warns[:3]` 只显示前三条；最终 summary 没有“跳过多少、为什么”。
- **最小修法**：在 snapshot/summary 里记录 `n_seen/n_used/n_skipped` 和原因计数；缺 json 也计入 skipped。

#### S7｜`UnitLibrary.from_csv` 用 `tab[:,0,0]` 当法向 Γ，若 CSV 首个 θ 不是 0 会错
- **file:line**：`gnn/msgnn/physics/unit_library.py:77-91`
- **问题**：`g = tab[:, 0, 0]` 假设 `th[0]=0, ph[0]=0`；没有断言。若表从 5° 开始，`gamma` 是 5° 的值，后续无表查询会静默用错。
- **最小修法**：找到 `theta_ax==0 & phi_ax==0` 的索引；若不存在，要求显式提供 `gamma` 或报错。

#### S8｜内部单位是 mm/deg，计划约定是 m/rad，转换因子散落在多处
- **file:line**：`gnn/msgnn/physics/radiation.py:35-46`（`C0_MM_GHZ`、`1e-3`）；`gnn/msgnn/data/build_graph.py:135`（λ 用 mm）；计划 `_tmp_spec/spec1.md:68`（位置/尺寸 m、角度内部 rad）
- **问题**：代码全链路用 mm 和 deg，只在 `const_c` 的 `1e-3` 里做 mm²→m² 的隐式换算；这与计划的统一约定（m/rad）不一致。数值上 19.342 自检证明当前换算是对的，但单位混用会让曲面面积、斜入射相位、以及未来导入 CST 米制几何时更容易出错。
- **最小修法**：至少在 `radiation.py` 顶部写一张单位表（输入 mm、内部 mm、输出 m²）；给 `const_c`/`area` 加显式单位测试；若要按计划统一到 m，先加一个 `length_unit` 配置并在入口转换，避免全包重写。

---

## 3 曲面预留能力矩阵

| 项目 | 状态 | 现有实现位置 | 最小改动路径 |
|---|---|---|---|
| 节点位置真三维 | **部分** | `gnn/msgnn/data/build_graph.py:114` 把 `pos` 拼成 `[x,y,0]`；`gnn/msgnn/physics/radiation.py:171,179` 的算子确实用 3D 位置做相位；节点特征只用 x/y（`build_graph.py:86-89`） | 增加 `Surface.positions(u,v)`，把 `pos` 作为参数传入 `build_graph`；节点特征加 `z/λ`；保留 `lattice_xy` 作为 R→∞ 的平面特例 |
| 局部坐标系 t1/t2/n | **缺失** | 只有标量 `normal_z`（`build_graph.py:13-14,84`），恒 1；没有 `frame[N,3,3]` | 加 `frame`，三列 `t1,t2,n`；由曲面参数化解析或数值微分得到；存进 graph 并写进 `geometry.npz` |
| 单元面积 | **缺失** | `radiation.py:44-46` 的 `const_c` 用全局 `P²`；`q` 的所有节点共享一个面积 | 逐节点 `area_n`；`C_n = 2√π/λ · area_n · 1e-3`；对曲面用实际面元面积（或投影面积×obliquity） |
| 法向/局部入射角 | **缺失** | 没有 `k̂_inc`，没有 `cosθ_loc`；只有 `normal_z` 占位 | 配置里加 `incident_k`/`polarization`；每节点算 `cosθ_loc = −k̂_inc·n`；`backlit = cosθ_loc <= 0` |
| 辐射算子接受任意 3D 位置与方向 | **部分** | 位置：`radiation.py:150-171` 接受 `pos_mm (N,3)`；观测方向：`directions()` `radiation.py:64-69` 是 3D 单位矢量；源方向：`projection_factors` `radiation.py:72-80` 是全局 x̂ | 把标量 `S·p` 改成逐节点矢量源求和 `E = C Σ (I−ŝŝ^T) q_n exp(jk r_n·ŝ)`（或每节点 2×2 极化率）；先用倾斜单源/双源解析测试 |
| 边特征含 3D 距离与法向夹角 | **缺失** | `gnn/msgnn/data/build_graph.py:93-99` 只用 `pos_xy`，5 维 `dx,dy,r,cos az,sin az` | 改用 3D `pos`：加 `dz/λ`、`r3/λ`、`n_i·n_j`、`angle(n_i, r_ij)`；保留 2D 作为平面特例 |
| 图从 (u,v) 参数化曲面生成 | **缺失** | `lattice_xy` `build_graph.py:41-44`、`edge_index_grid` `build_graph.py:57-73`、`build_graph` `105-111` 全是方阵 | 加 `ParametricSurface`（positions/frame/area/neighbours）；`edge_index` 仍可由 (i,j) 网格生成，只替换 positions/frame；平面是 `R=∞` 的特例 |
| 配置/数据集 curvature/radius/frame 字段 | **缺失** | `PhysicsCfg` 只有 freq/n_side/block/period/projection/gamma_source/unit_table/patch_r_mm（`config.py:50-59`）；`Case` 只有 code/bits/layout（`dataset.py:113-129`） | 加 `geometry: {surface, radius_mm, axis, u_range, v_range}`；`Case` 加 `radius/frame_path`；graph 存 `frame/area` |
| 遮挡与背照标记 | **缺失** | 没有 `visible/backlit`；`unit_library.return_oob` 从未被管线调用（`unit_library.py:136-137`） | 每节点 `backlit = cosθ_loc <= 0`；圆柱可用简单的 front-facing/ray-cylinder 遮挡；把 mask 传入 loss/metrics；对剧烈弯曲另加 `approx_valid` 标记 |
| 指标支持观测域掩码 | **部分** | `evaluate.py:71-91` 只按 θ 区间和 `t >= meas_floor_db` 掩码；`losses.py:75-79` 只有 null mask，不是可见性 mask | 给 `Grid/Case` 加 `obs_mask[M]`（bool）；loss/metrics 统一乘 mask；默认排除 θ=90；配置 `eval.grazing_min_theta` |
| 曲率/局部平面近似标记 | **缺失** | 没有曲率；只在文档里说“投影是平面近似”（`REPORT.md:399`） | 每节点存局部曲率/半径；`planar_ok = (cell_size/R < tol)`；对超限节点/样本打标并单独报告 |
| 相位原点/参考面 | **部分** | q=Γ 的 S11 参考面隐含在数值里，但没有字段；远场只保留相对相位（`radiation.py:4-10,179`） | `UnitMeta.reference_plane`；`phase_ref`；复场标签先做全局相位标定 |
| 源基函数 K/方向/单位 | **缺失** | q 是标量、K=1（`radiation.py:146-148`；`baseline.py:29-31`） | 定义 `K`、源类型、方向、单位、面积；先实现 K=1 的 x̂ 电偶极子并显式写清，再扩 K>1 |
| 不同节点数批处理 | **已具备** | `collate` 的 `ptr`/`batch`（`build_graph.py:177-205`）；`pipeline.forward` 的不等长分支（`pipeline.py:70-87`） | 不需要改；曲面时保持 |
| 节点重排不变 | **已具备** | `tests/test_graph.py:91-157` 的算子级/整模型级测试 | 曲面时把 `pos/frame` 一起置换，保持该测试 |

---

## 4 越界改动清单

> 判定口径：“合理扩展”=超出计划但为工程/诊断所需，且不改变物理默认；“可疑越界”=超出计划且可能改变结论/默认/数据契约，或承诺了未实现的能力。

| # | 位置 | 超出要求的内容 | 判定 | 理由/最小处理 |
|---|---|---|---|---|
| 1 | `gnn/msgnn/inference.py:11-31` | 额外的 shared inference 模块 | **合理扩展** | 只是 train/evaluate/predict 的去重封装，没有新物理；保留 |
| 2 | `gnn/msgnn/experiment.py:85-162` | 额外的 context 构建模块 | **合理扩展** | 把 snapshot/split/normalizer/operator 固定在一处，正好是防泄漏所需；但 `:125-133` 的 max_cases 硬编码是可疑默认（见 M11） |
| 3 | `gnn/msgnn/models/cnn_baseline.py:11-17,50-58,84-90` | M1 的 rank-4 因子化读出 + 可学习 `sky` 偏置 + 全局 `out_scale` | **可疑越界** | 计划只要求 CNN/U-Net 直接回归；`sky` 是“平均方向图”先验，`out_scale` 可吸收绝对电平，可能让 M1 这个“无物理对照”偏强。建议在 REPORT 明确标注偏离，并做去掉 sky/out_scale 的消融 |
| 4 | `gnn/msgnn/physics/baseline.py:55-122` | 每样本 1 个复标量的 oracle 拟合（M0g） | **合理扩展** | 明确标注 oracle、只用标签拟合、不参与训练；作为“2 个实自由度能解释多少”的上界是合理的 |
| 5 | `gnn/msgnn/physics/unit_library.py:44-50` | `gamma_source='unit'`（|Γ|=1） | **合理扩展** | 诊断用，默认仍是 floquet（符合用户给的 Γ）；需在报告中说明它不是“更真实”，只是去掉数值损耗 |
| 6 | `gnn/msgnn/physics/unit_library.py:77-91,101-137` + `config.py:58` | 角度相关 CSV 插值 + `unit_table` | **可疑越界** | 代码/配置承诺了斜入射扩展，但 `build_context` 从不加载，`build_graph` 不传角度，也没有测试；当前是死代码。要么接线，要么删掉/标注 TODO |
| 7 | `gnn/msgnn/config.py:32,38-40,59,123` | `codes_subdir`、`max_samples`、`cache`、`patch_r_mm`、`seeds` | **可疑越界** | 这些字段从未被消费（`grep` 只命中定义/校验）；配置看起来可调，实际无效。建议删除或接线，并在 config 测试里加“字段被使用”的清单 |
| 8 | `gnn/msgnn/losses.py:14-17,60-64,75-80` | asinh 压缩、null 项、mainlobe boost | **合理扩展** | 都是为了适配 25–30 dB 动态范围；`REPORT.md:167-199` 有说明和消融口径。但 mainlobe boost=3 是主观选择，必须在结果里同时给 boost=1 的对照 |
| 9 | `gnn/msgnn/losses.py:110-115` | complex 模式的逐方向相对归一化 | **可疑越界** | 与计划 `sum w|ΔF|²/(sum w|F|²+eps)` 的全局分母不同；会抹掉绝对电平敏感性（见 M9）。建议默认关闭 `complex_compress`，或两种口径并列 |
| 10 | `gnn/msgnn/evaluate.py:110-136` | M0g oracle 进入统一评估表 | **合理扩展** | 命名清晰、报告里反复标注 oracle；保留 |
| 11 | `gnn/msgnn/evaluate.py:57-58` | 先把 pred/targ 截到 −60 再算 `rho_lin` | **可疑越界** | 这是一个隐藏的指标假设，不是数据契约；会改变头条指标（见 M7）。改为 `rho_lin` 用原始线性功率，floor 只用于 dB 域 |
| 12 | `gnn/msgnn/__init__.py:14-21` | 包导入时设置 `KMP_DUPLICATE_LIB_OK=TRUE` | **可疑越界** | 库不应该在 import 时改全局环境；可能掩盖 OpenMP 冲突。移到启动脚本/文档 |
| 13 | `gnn/runs/verify/` | 一份完整的 shadow `msgnn` 副本 + 旧测试 + 复核报告 | **越界杂物** | 不是交付代码，容易混淆导入/审计；移到 `docs/reviews/artifacts` 或删除（见 S3） |
| 14 | `gnn/msgnn/config.py:39` | `complex_ff` 默认指向 `D:/ff_er265_r2_b2/ff_10.txt` | **可疑越界** | 仓库外绝对路径成为默认值；换机后静默 skip。默认 `None`，显式传参 |
| 15 | `gnn/msgnn/experiment.py:125-133` | max_cases 的 0.7/0.15/0.15 硬编码 | **可疑越界** | 覆盖了 `data.val_frac/test_frac`，且不写进 config；见 M11 |

---

## 5 还缺什么（按优先级，供下一轮开发）

### P0｜在扩曲面/复数之前必须钉死

1. **q 的源基函数定义 + 逐节点面积/方向**（B2）：写清 `q` 是“归一化 x̂ 电偶极子系数”，把 `area_n`、`frame` 传进辐射层；否则曲面的“q”没有可解释的物理量纲。
2. **complex 路径 + 相位标定**（B1、M1）：要么明确禁用，要么补 1°/2° 网格、dict 目标、全局相位/共轭；先在唯一的 6 列样本上验证相位。
3. **b 与 Δq 的分离**（B3）：centering 或删 b；否则“|b|≈0.37”的归因不成立，REPORT 的验收判据要重写。
4. **4/6 列数据契约**（M4）：幅度路径只接受 4 列，6 列走 complex；否则未来换导出格式会静默算错。

### P1｜在相信指标之前

5. `rho_lin` 去截断、排除 θ=90、补 6–60（M7）。
6. E/H 面指标 + 可选 per-component loss（M8）。
7. 快照 sha256 校验（M5）；summary 打印 `n_cases/n_groups`，n_cases==n_groups 时标注“i.i.d.”（M6）。
8. `test_config_roundtrip` 修复（M13）；清理 `unit_table/max_samples/cache/patch_r_mm/seeds` 死配置（M2、越界 #7）。
9. 单元库元数据（M3）：εr/tanδ/h/P/r/端口/模式/参考面。

### P2｜曲面扩展

10. **geometry provider**：`ParametricSurface(u,v) → pos[N,3], frame[N,3,3], area[N]`；平面是 `R=∞`；graph builder 只替换 positions/frame，`edge_index` 拓扑可不变。
11. **3D 边特征**：`dz/λ, r3/λ, n_i·n_j, angle(n_i, r_ij)`；现有 2D 特征作为平面特例。
12. **入射/遮挡/背照**：`k̂_inc`、`cosθ_loc`、`backlit`、圆柱 front-facing/ray 遮挡；`library_flags` 记录越界。
13. **观测域掩码**：`obs_mask[M]` 进入 loss/metrics；默认排除 θ=90；支持 0–180 的背照数据。
14. **Huygens/低阶源验证**：REPORT 自认未做（`REPORT.md:309`）；在扩曲面之前补一个闭合面或解析单源/双源验证，否则无法区分“源表示不足”和“GNN 误差”。
15. **M2/M3 消融控制**（M10）：M3-noglob、M2+q0；否则 M3−M2 不能解释为残差形式的价值。

---

## 附录 A 数据现场只读核对

| 项 | 结果 |
|---|---|
| `D:/dataset/results/ff/ff_*.txt` | **266** 个（`Get-ChildItem ... Measure-Object`） |
| `D:/dataset/results/res_*.json` | **266** 个 |
| `ff_0000.txt:1` | `0 0 10.7983454476387 -40.3455059051381`（θ=0, φ=0, Eθ dBsm, Eφ dBsm） |
| `ff_0000.txt:8280` | `90 358 -25.1258341216851 -31.8544523015787`（θ=90, φ=358） |
| `res_0000.json:1` | code 100 字符、`block=2`、`specular_dbsm=10.798`、`mean_far_dbsm=-6.559`、`freq_ghz=10.0`、`ff_step=2.0` |
| `ff_10.txt:1` | `0 0 10.7983454476387 55.5595891920452 -40.3455059051381 261.20890814357`（6 列，含相位） |
| `ff_10.txt:65160` | `180 359 19.3751103199172 167.810732501964 -15.7658873414155 347.858369329877`（1°、0–180、0–359） |
| `ff_10.txt` 的 θ=180 电平 | 19.375 dBsm，逼近 PEC 板 19.342；与 `theory/REPORT.md:460` 的“θ=180 瓣 19.376 dBsm”一致，是数据绝对标定的独立旁证 |
| 冻结快照 | `gnn/runs/verify/ctx/snapshot.json:10` `n=247`；`gnn/runs/verify/ctx/splits.json:5-6` `n_cases=247, n_groups=247` |
| 既有实测（非本次运行） | case 0000 vector：θ6–60 ρ 0.899/RMSE 2.81；θ6–90 ρ 0.770/RMSE 6.50；镜面 −3.01 vs 10.80 → −13.81 dB；25 例 M0 vector 6–90 ρ 0.780/RMSE 6.40/bias −0.59（`gnn/runs/verify/REPORT_verify.md:56-61`） |

> 说明：目录里现在是 266 例，而冻结快照是 247 例（08:54 生成）。这是“CST 仍在产出”的正常现象；任何新训练都应重新冻结，不能把 266 例直接塞进 247 例的 split。

## 附录 B 未能确认 / 未执行

1. **CST 相位/时间约定**：未运行，未将 `ff_10.txt` 的相位与算子逐点比较；只知道 θ=0 的 Eθ 相位 55.56°，不足以判定符号。代码写的是 `+jk r·s`，在 exp(+jωt) 下是相对相位；CST 是否同约定**未能确认**。
2. **测试是否全绿**：本次未执行 pytest。静态推演：`test_config_roundtrip` 会因 `eval.bands` 的 tuple/list 往返失败（M13）；其余测试从代码看与当前形状/断言一致，但**未运行确认**。
3. **当前 266 例是否都能通过 `_ff_is_valid`**：只抽查了 `ff_0000`；未逐文件扫描。
4. **M3 训练后的 |b|、Δq 统计**：未训练；REPORT 的 0.37 是 theory 的既有拟合，不是本包的实测。
5. **E/H −1.84 dB / −1.61 dB 在 gnn 管线中的复现**：未运行；代码只有投影因子的单元测试，没有 E/H 面均值指标。
6. **19.342 的本次复跑**：未运行；引用的是代码断言 + 既有实测（`gnn/runs/verify/REPORT_verify.md:30-34`）。

---

*审计结论以本报告为准；未改任何源文件。*
