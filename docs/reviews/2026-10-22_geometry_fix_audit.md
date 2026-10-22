# 几何修复复核审计（2026-10-22）

> 审计对象：工作区**未提交**改动，HEAD `a971f5b`（`main`）。
> 范围：上一轮 `docs/reviews/2026-10-22_geometry_audit.md` 指出的 **F1 / M1 / M3 / M4 / M5** 五条。
> 方法：**只读静态审查，未运行 Python / pytest，未改源码**；只使用 `git status` / `git diff`、源码与文档阅读。`git status` 为 3 个已跟踪修改（config/build_graph/experiment）+ 新 `geometry.py` / `test_geometry.py` / 3 个文档；无新依赖、无默认值改动。
> 结论：**有条件通过**。F1、M1、M3、M4 真修好；**M5 未通过**——测试文件语法正确，但含 1 条恒真断言、1 条必失败断言、1 个缺失 fixture，整套测试按现状不会绿。按现状**不允许提交/推送**；修好测试与文档漂移后可提交。

## 1 摘要（≤20 行）

- **F1 ✅ 通过**：`frames()` 已按列填，`t1=(cosθ,0,−sinθ)`、`n=(sinθ,0,cosθ)`、`t1×t2=n`，`k_t1=+sinθ`；`normal_z/frames[:,:,2]/incidence` 三个消费者均按列一致（§3）。
- **M1 ✅ 通过**：模块 docstring 已改为“中心最高、向 +z 凸、即照射侧”（`geometry.py:27-30`）。
- **M3 ✅ 通过**：`from_config` 对 plane 返回 `None`（`geometry.py:145-150`）；`_validate` 拒绝 `geometry=true & surface=plane`（`config.py:289-294`）。
- **M4 ✅ 通过（按字面要求）**：`experiment.py:24` 已 import；`:153-166` 用 `surface.positions()/areas()` 建算子；plane 分支仍用 `R.lattice_positions` 且 `area=None`（`:155-156`）。
- **M5 ❌ 未通过**：`tests/test_geometry.py:43/47` 确实能抓 F1，但 `:37` 是恒真断言，`:57` 必失败，`:95` 依赖的 `env` fixture 只在 `test_graph.py` 里定义；见 §5。
- `geometry=false` 静态判断逐位不变（未实测）：9/5 列、表达式与求值顺序未变；但“无新分支”不成立（新增 `from_config`、`surface is None`、`geom is not None` 分支，均为惰性），文档 `geometry_representation.md:45` 仍写错。
- **新不一致（旁路）**：M4 让 GNN 算子改成 3D 曲面位置，但 `evaluate.py:124` 的 M0/M0g 基线仍用平面 `lattice_positions`；`geometry=true` 时同一评估里 GNN 与基线几何不一致（§7-I1）。
- **新不一致（语义）**：`build_graph.py:136` 令 `pos_xy=pos[:,:2]`，`edge_features` 仍算 2D 投影距离，边上又追加 3D `r3d`；柱面上 `r_lam≠r3d_lam`，文档未标注“2D 投影”（§7-I2）；属上一轮已有设计，不是五条修复引入。
- **文档漂移**：`docs/geometry_representation.md:57` 仍说面积未接入（M4 已接入）；`:45`、`:29`、`geometry.py:2`、`build_graph.py:13-14` 均有旧话（§7-I3）。
- **越界**：未发现五条之外的源码行为改动、新依赖、默认值或接口重命名；`build_graph` 的几何块是上一轮已审计特性（§8）。
- **提交结论**：当前**不允许**提交/推送；先修 `test_geometry.py` 与文档，再提交。即使修好，`geometry=true` 仍不能宣称“曲面表征已补齐”（M2/M4 限制仍在）。

## 2 逐条核验表

| # | 上一轮要求 | 实际证据（file:line） | 判定 |
|---|---|---|---|
| **F1** | `frames()` 改为按**列**填；柱面 u=0 处 t1=(1,0,0)、n=(0,0,1)；一般 u：t1=(cosθ,0,−sinθ)、n=(sinθ,0,cosθ)、t1×t2=n；`incidence` 的 k_t1=+sinθ | `gnn/msgnn/data/geometry.py:82-101`（`f[:,0,0]=cos`、`f[:,2,0]=−sin`、`f[:,1,1]=1`、`f[:,0,2]=sin`、`f[:,2,2]=cos`）；`:103-104` normals；`:119-135` incidence；消费者 `build_graph.py:137,151` | ✅ 通过（§3 独立推导） |
| **M1** | docstring 改为“向 +z 凸、中心最高、即照射侧” | `geometry.py:27-30`：“The centre (u=0) is the highest point and the surface is convex towards +z, which is the illuminated side (cos_inc = +1 there); z <= 0 away from the axis.” | ✅ 通过 |
| **M3** | `from_config` 对 plane 返回 None；`_validate` 拒绝 geometry=true + plane | `geometry.py:138-150`（非 geometry 返回 None；plane 返回 None）；`config.py:287-294`（surface 取值校验；geometry+plane 抛 `ConfigError`；cylinder 半径 >0） | ✅ 通过 |
| **M4** | `experiment.py` 用 `surface.positions()/areas()` 建算子；import 已加；plane 分支仍 `R.lattice_positions` 且 area=None | `experiment.py:24`（import）、`:150-166`（`surface=geometry.from_config`；plane `:155-156`；cylinder `:158-159`；`area_mm2=area` `:166`）；`radiation.py:162-200` 支持 per-node area | ✅ 通过（按字面；旁路见 §7-I1） |
| **M5** | 新增测试，比较 `frames[:,:,0]` 与解析导数，不能是恒真；文件语法正确 | `tests/test_geometry.py:31-57` 有解析比较；但 `:37` 恒真、`:57` 必失败、`:95` 缺 fixture；共 6 个用例（非回应文档所称 7 个） | ❌ 未通过（§5） |

## 3 F1 的独立推导

柱面参数化（`geometry.py:77-80`）：

    θ = u / R
    r(u,v) = ( R sinθ,  v,  −R(1−cosθ) )
    r_u = ( cosθ, 0, −sinθ ) = t1,   ‖t1‖=1
    r_v = ( 0, 1, 0 )       = t2,   ‖t2‖=1,  t1·t2=0
    n = t1 × t2 = ( sinθ, 0, cosθ ),  ‖n‖=1

u=0：t1=(1,0,0)、t2=(0,1,0)、n=(0,0,1)。k=(0,0,−1) 时：

    cos_inc = −n·k = cosθ          （u=0 为 +1）
    k_t1    = t1·k = +sinθ        （旧行/列转置给 −sinθ）
    k_t2    = t2·k = 0

当前 `frames()` 的 3×3 矩阵（每个节点）为：

    F = [[ cosθ,  0,  sinθ ],
         [ 0,     1,  0    ],
         [-sinθ,  0,  cosθ ]]

即 **列 0 = (cosθ,0,−sinθ) = t1**、列 1 = (0,1,0) = t2、列 2 = (sinθ,0,cosθ) = n；`t1×t2=n`，det=+1。`frames[:, :, 0/1/2]`、`normals()`、`incidence()`、`build_graph.py:137`（`frames[:,2,2]=n_z`）与 `:151`（`frames[src,:,2]`）全部按列使用，已无行/列错位。

u=0 在 `n_side` 为偶数时不是采样点（`grid_uv` 取半整数倍 P，`geometry.py:66-70`）；因此只能解析验证 u=0 的极限，不能靠 N=8 的节点验证，这一点测试没有误用。

## 4 M1 / M3 / M4 细节

### 4.1 M1

`geometry.py:27-30` 原文已满足要求：中心 u=0 是最高点（z=0），曲面朝 +z 凸，+z 是照射侧，cos_inc=+1；z≤0。未在仓库其它文档发现旧的“bulges towards −z”残留（只有上一轮审计报告引用旧文）。✅

### 4.2 M3

- `from_config()`：`getattr(graph_cfg,"geometry",False)` 为假 → `None`；geometry=true 时构造 `Surface(...).check()`，若 `is_plane` → `None`（`geometry.py:138-150`）。因此只写 `geometry: true` 不会再静默变 15/7 列。
- `_validate`：surface 只允许 plane/cylinder；geometry=true 且 plane 直接报 `ConfigError`；geometry=true 且 cylinder 要求 `surface_radius_mm>0`（`config.py:287-294`）。
- 小边界：geometry=false 时 cylinder+radius=0 仍能通过校验（随后 `from_config` 返回 None，惰性）；不是本轮阻断项。

### 4.3 M4

- `experiment.py:24`：`from .data import geometry`。
- `experiment.py:153`：`surface = geometry.from_config(cfg.graph)`。
- plane：`:155-156` `pos = R.lattice_positions(...)`、`area = None`。
- cylinder：`:158-159` `pos = surface.positions(...)`、`area = surface.areas(...)`；`:160-166` 传给 `FarFieldOperator(pos_mm=pos, area_mm2=area)`。
- `radiation.py:188-200,250-254`：area 路径把源强改为 `q_n·A_n` 并把 `P²` 从常数中移出；对 `A_n=P²` 与旧平面路径数学等价（浮点上因 `q·P²` 与常数重排可能有 rounding；文档亦如此写），对柱面则相位用 3D 位置。按 M4 的字面要求已通过。
- 限制：`collate` 仍不带 `pos/frame/area/curv`（`build_graph.py:221-249`），GNN 本体看不到 3D 位置/完整 frame；M4 只修了“物理算子”，没有修“网络输入链路”。回应文档已把它列为 P1，属实。

## 5 M5 测试静态分析（关键）

文件语法**静态正确**：括号/缩进/import/装饰器均平衡，`GEOM_NODE_FEATURES`、`GEOM_EDGE_FEATURES` 均存在。但语义有三处硬伤：

1. **恒真断言**：`tests/test_geometry.py:37`
   `assert np.allclose(f[:, :, 0], s.frames(N, P)[:, :, 0])`
   左右是同一实现的两次调用；F1 回归时两边一起变，永远通过。应删除。

2. **必失败断言 / 假“有限差分”**：`tests/test_geometry.py:52-57`
   `idx = 1  # one step along u` 是错的：`grid_uv` 用 `np.meshgrid(a, a, indexing="ij")`（`geometry.py:66-70`），C-order `ravel()` 使 index 1 = (u₀, v₁)，即 **v 方向**邻居，不是 u 方向。实际 `dvec = (0, P, 0)`，而断言期望 `(P cosθ₁, 0)`（θ₁=−49/200≈−0.245，约 13.58），在 `atol=1e-9` 下必然失败。
   即使把 index 改成 u 方向，用“一个单元的两端点之差”对比“端点处切向量”也不是有限差分：弦长 `2R sin(P/2R)` 与切线 `P` 差 O(P³/R²)，仍不可能过 1e-9。`:39` 的 `du=1e-4` 和 `:40` 的 `sp` 均未使用，说明这段并未真的做有限差分。

3. **缺失 fixture**：`tests/test_geometry.py:95` 的 `env` 只在 `tests/test_graph.py:23-30` 定义；pytest 的测试模块 fixture 不会跨模块导出，`gnn/conftest.py:1-8` 只加 `sys.path`，`gnn/pytest.ini` 也无插件。因此该用例在 setup 阶段报 `fixture 'env' not found`（error），不是 pass/skip。

正面结论：`:42-43` 用解析 `t1_ref=(cosθ,0,−sinθ)` 比较 `frames[:,:,0]`，`:46-47` 用 `n_ref=(sinθ,0,cosθ)` 比较 `frames[:,:,2]`；若 F1 复发行填，这两条会失败。因此“测试能抓住 F1”这一半是真的，但**文件整体不可运行/不可绿**，M5 不能算完成。另外 `:49-51` 的 `t1×t2=n` 与行范数在转置下也成立，抓不住 F1；`:37` 更是无效。

## 6 geometry=false 路径的回归判断

**静态结论：9/5 列、数值表达式与求值顺序未变。**

- `node_features`：`build_graph.py:92-95` 前 9 个表达式与 HEAD 的 `:86-89` 逐项相同（`b, 2b−1, x/λ, y/λ, ReΓ, ImΓ, |Γ|, boundary, nz`），`geom=None` 时跳过新增块，最后同一个 `np.stack(cols,axis=1).astype(np.float32)`。
- `build_graph`：`surface=None` 分支 `pos_xy=lattice_xy`、`pos=concat(...,0)`；`edge_features` 函数体未改；几何边块被 `surface is not None` 跳过（`build_graph.py:126-152`）。
- `GraphDataset`：`from_config` 在 false 时返回 None，之后调用 `build_graph(..., surface=None)`（`build_graph.py:179-185`）。
- `experiment`：plane 分支仍 `R.lattice_positions`、`area=None`；`FarFieldOperator(area_mm2=None)` 等价旧默认（`experiment.py:155-166`；`radiation.py:190-200`）。
- 返回字典只多 `frame/area/curv=None` 三个惰性键（`build_graph.py:158-160`）；`collate` 不读它们，`get` 也不 tensor 化它们。

但“**无新分支**”的字面说法不成立：`GraphDataset` 无条件调用 `from_config`（`build_graph.py:179`），`build_graph` 有 `if surface is None`（`:126`），`node_features` 有 `if geom is not None`（`:96`）。它们是惰性分支，不改变 false 路径数值，但文档 `docs/geometry_representation.md:45` 仍写“不走任何新代码分支”，是错的。未运行 Python，故只能给表达式/顺序层面的静态结论，不能给字节级证据。

## 7 新发现与遗留问题

### I1（重要，旁路不一致）M4 只修了 GNN 算子，M0 基线仍按平面

- `gnn/msgnn/evaluate.py:124`：`pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)`，与 `geometry` 无关；`:128-130` 把它传给 `BL.field_terms`。
- `gnn/msgnn/physics/baseline.py:125-137`：`field_terms` 用该 `pos` 做 `aperture_sum_numpy`，`c=R.const_c(...)` 仍是 P²。
- 结果：`geometry=true`（柱面）时，GNN 的 `ctx.operator` 用 3D `surface.positions`，而 `predict_baseline` 的 M0/M0g 仍用平面位置；同一 `metrics.csv` 里两类模型不是同一几何。M4 之前两者都是平面（对曲面目标一致地错）；M4 之后变成“GNN 曲面、基线平面”的新分歧。未影响 `geometry=false`；修法：`predict_baseline` 也用 `geometry.from_config(cfg.graph)`，或明确在文档/指标里标注基线是平面参考。

### I2（重要，语义不一致）2D 投影边特征与 3D r3d 并存

- `build_graph.py:136`：`pos_xy = pos[:, :2]`（柱面时是 `x=R sinθ, y=v` 的**投影**坐标）；
- `build_graph.py:144-145`：`edge_features(ei, pos_xy, lam)` 仍只算 `dx,dy,r` 的 2D 量；
- `build_graph.py:150-152`：又追加 `d3=‖pos[dst]−pos[src]‖/λ` 与 `mism`。
- 柱面上水平边：`r_lam = 2R cos(θ+P/2R) sin(P/2R)`，`r3d_lam = 2R sin(P/2R)`，二者不相等；`dx_lam` 是投影弦差，不是弧长差。两者作为特征可以并存（2D 孔径投影 + 3D 真实距离），但 `EDGE_FEATURES` 文档（`build_graph.py:16-17`）仍写“dx,dy,r/lambda”，没有标注“projected”，容易被误读为同一物理距离。
- 这**不是五条修复引入的**：`edge_features()` 函数体相对 HEAD 未改，上一轮审计 §3.4 已按 3D `pos` 讨论 `d3`；但 M4 把算子改成 3D 后，这个 2D/3D 混用更值得处理。建议：文档标注，或把 `dx/dy/dz` 与 `r3d` 一起用 3D，2D 版本另起列。

### I3（重要，文档漂移）

- `docs/geometry_representation.md:57`：“面积进入远场求和……尚未由 build_graph 的 area 自动接入”已过时——M4 在 `experiment.py:158-166` 用 `surface.areas()` 直接接入 `FarFieldOperator(area_mm2=...)`；应改为“已接入，但只对全局单曲面”。
- `docs/geometry_representation.md:45`：“geometry=false 时不走任何新代码分支”仍错（见 §6）。
- `docs/geometry_representation.md:29`：承诺边特征含“曲率差 |κ1_i−κ1_j|”；实现仍只有 `r3d_lam, normal_mismatch`（`build_graph.py:42`）。
- `geometry.py:2`：“planar now, cylindrical next”已过时（cylinder 已实现）；`build_graph.py:13-14`：“normal_z ... slot reserved for the cylindrical / conformal extension”与现状不符（cylinder 已实际写入 normal_z）。
- 次要：`docs/gnn_architecture.md:28-29`、`gnn/REPORT.md:134` 仍只写 9/5，未注明可选 15/7；上一轮 S6 已列。

### I4（建议）`build_graph` 仍不调用 `surface.check()`

- `build_graph.py:121` 接受任意 `Surface`；`:131-135` 直接调用方法。若调用方传入 `Surface(kind="cylinder", radius_mm=0)`（不经 `from_config`），`geometry.py:77-80` 会除零产生 NaN，而不是报错。`from_config` 路径安全，但公开 API 仍可误用。上一轮 S3，未处理。

### I5（建议/次要）

- `GraphDataset`（`build_graph.py:179`）与 `build_context`（`experiment.py:153`）各构造一次 `Surface`；每个 case 又在 `build_graph.py:131-135` 重算 positions/frames/areas/curvature/incidence。功能正确，纯重复。
- 回应文档 `docs/reviews/2026-10-22_geometry_audit_response.md:14` 称“7 个用例”，实际 6 个（`test_geometry.py:20,31,60,75,85,95`）；且“修完 M5”与实际不符。
- `test_geometry.py:39,40` 的 `du`、`sp` 未使用；`:51` 的 `np.linalg.norm(f, axis=1)` 检查的是行范数，不是列（基向量）范数；在本矩阵上恰好也过，属于弱断言。

## 8 范围 / 是否越界

- `git status`：仅 `gnn/msgnn/config.py`、`gnn/msgnn/data/build_graph.py`、`gnn/msgnn/experiment.py` 三个已跟踪修改；新文件 `gnn/msgnn/data/geometry.py`、`gnn/tests/test_geometry.py`、`docs/geometry_representation.md`、两份 review 文档。无 requirements/setup 改动、无新第三方依赖、无重命名、未改 `geometry=false` 默认值。
- 五条之外**未发现源码行为越界**：F1 只动 `geometry.py` 的 fill 与注释；M3 只动 `from_config` + `_validate`；M4 只动 `experiment.py` 的算子构造；M5 只加测试；`build_graph` 的几何块（含 `pos_xy=pos[:,:2]`）是上一轮已审计的特性，本轮未改 `edge_features` 函数体。
- 但 **M4 的文档没有同步更新**（`docs/geometry_representation.md:57`），这是遗漏而非越界；回应文档 `..._response.md` 是流程产物。
- 注意：`build_graph.py` 的 `pos_xy=pos[:,:2]` 与 `r3d` 混用（I2）虽然旧，但 M4 使“物理 3D、网络 2D”的分离更明显；若要本轮一并清理，应视为新的设计决定，需单独测试。

## 9 是否允许提交

**按现状不允许提交/推送。** 理由：

1. `tests/test_geometry.py` 至少 `:57` 必失败、`:95` 必 error；提交后 `pytest` 不会是绿的，违反 M5 的“新增可运行测试”要求，也违反 `docs/CONVENTIONS.md:52-63` 的“处理完毕才 push”。
2. 回应文档宣称 M5 已修，与实际不符；文档 `geometry_representation.md:57` 与 M4 实现相反。

**修好以下项后可提交**：

- 删除/重写 `test_geometry.py:37` 的恒真断言；
- 修 `:52-57`：用真正的中心差分（构造 u±du 的位置，或直接比较解析 `t1_ref`；当前 `:43` 已足够，可删掉假 FD 段），并修正“index 1 是 v 邻居”的方向；
- 把 `env` fixture 移到 `gnn/conftest.py`（或在本文件内定义），并给 `test_graph_feature_widths...` 加数据集缺失时的 skip；
- 更新 `docs/geometry_representation.md:45,57`、`geometry.py:2`、`build_graph.py:13-14`；
- 修完在目标机实际跑 `pytest gnn/tests/test_geometry.py`（本轮按指令未运行；报告只能证明上述断言的静态失败）。

即便修好测试，`geometry=true` 仍**不应宣称“曲面表征已补齐”**：M2 的 6 列在单一 R/正入射下仍退化，M4 的网络输入侧仍缺 `pos/frame`，I1 的基线仍平面，I2 的 2D/3D 语义未统一；这些属于 P1，不是本轮五条的阻断项，但必须在文档中明说。

## 10 限制（未能确认）

- 未运行 Python/pytest：不能给“逐位不变”的字节级证据，§6 是表达式/求值顺序层面的静态结论；§5 的 `:57` 失败是解析推导，不是实测。
- 仓库内没有曲面数据集/逐 Case 半径（`Case` 无 radius），无法验证 CST 目标是否按同一 3D 几何生成；M4 的 3D 相位与标签一致性**未能确认**。
- 未确认 `Surface.check()` 是否会被其它外部调用方绕过（§I4）；未确认 `geometry=true` 的实际训练是否会用到 `evaluate.predict_baseline`（§I1），故 I1 定为“重要/旁路”而非阻断。