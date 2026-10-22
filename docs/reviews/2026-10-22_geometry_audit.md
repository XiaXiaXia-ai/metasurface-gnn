# 曲面几何表征审计（2026-10-22）

> 审计对象：工作区**未提交**改动，HEAD `a971f5b`（`main`）。
> 范围：`gnn/msgnn/data/geometry.py`（新）、`gnn/msgnn/data/build_graph.py`、`gnn/msgnn/config.py`、`docs/geometry_representation.md`（新）。
> 方法：**只读静态审查，未运行任何代码或测试**。`git status` 仅上述 4 个文件（2 改 + 2 新）；`git diff --numstat` = config +9/−0、build_graph +54/−10；`git diff --check` 无空白错误（只有仓库既有的 Windows autocrlf 提示）。

## 1 一句话结论

**有条件通过**：默认 `geometry=false` 的平面路径逐位不变、配置向后兼容，曲率与面积公式静态正确；但 `geometry=true` 路径存在**阻断级 frame 布局错误**（`k_t1` 反号、`normals()` 返回镜像法向，F1；`geometry.py:82,93-97,130-132`），并且新增列在当前“平面 / 单一半径柱面 / 正入射”下全部是常量或既有列的重复（`cos_inc` 与 `normal_z` 逐位相同，M2；`build_graph.py:96-104,137-140`）。F1、M1、M3、M5 修复前，只能作为**默认关闭的骨架**入库，不得启用 `geometry=true`，也不得宣称曲面表征已正确。

## 2 逐项核验表

| # | 声称项 | 实际（file:line） | 判定 |
|---|---|---|---|
| 1 | 范围：只改 3 个源码文件 + 1 个新文档，无新依赖/重命名/格式大改 | `git status` 仅这 4 个文件；`git diff --numstat` 见上；未改 requirements/setup；`geometry.py` 只用 stdlib + numpy | ✅ 通过 |
| 2 | 新增 `Surface`（plane/cylinder）与 positions/frames/areas/curvature/incidence | `gnn/msgnn/data/geometry.py:43-132` 六个接口齐全 | ✅ 通过 |
| 3 | 圆柱参数化 `x=R sin(u/R), z=−R(1−cos(u/R)), y=v`，t1/t2/n 右手、n 指反射侧、u=0 为 +z | `geometry.py:71-98`；行向量满足 t1×t2=n、det=+1、u=0 时 n=+z（§3.1） | ⚠️ 几何正确，但 frame 按行存、按列读（F1） |
| 4 | κ1=1/R、κ2=0、H=1/(2R)、K=0 | `geometry.py:107-114`；dn(t1)=t1/R、dn(t2)=0，H=½tr(dn)，K=0（§3.2） | ✅ 通过（符号约定未写明） |
| 5 | cos_inc=−k̂·n；k̂=(0,0,−1) 时 u=0 为 +1 | `geometry.py:131-132`；u=0 正入射确为 +1，正入射下所有 u 也正确 | ⚠️ k_t1 在 u≠0 反号（F1）；斜入射时 cos_inc 也会错 |
| 6 | k_t1、k_t2 是 k̂ 在局部系的分量 | 柱面 k_t1 实得 −sin(u/R)，正确为 +sin(u/R)；k_t2=0 巧合正确（`geometry.py:130-132`） | ❌ 错误（F1） |
| 7 | 边特征 1−n_i·n_j 在平面恒 0；r3d/λ 退化为 r/λ | `build_graph.py:150-151`；在 surface=plane 时点积=1.0 → 0.0；d3=hypot(Δx,Δy)/λ≈r/λ（实现顺序不同，非逐位；geometry=false 时这两列不存在） | ✅ 通过 |
| 8 | 面积 A=P² 与弧长参数化自洽、单元无拉伸 | `geometry.py:65-79,103-105`；‖r_u×r_v‖=1 精确，A=P²；同时 A/P²≡1 | ✅ 通过（该列恒 1，见 M2） |
| 9 | 节点 9→15 列、边 5→7 列、追加顺序与文档一致 | `build_graph.py:39-42,96-104,146-152`；geometry=true 时为 15/7 | ✅ 列数正确（信息量见 M2；边列依赖 edge_features，见 S7） |
| 10 | frame/area/curv 进图字典 | `build_graph.py:153-163`；surface=None 时为 None | ✅ 通过（但 collate 不带，见 M4） |
| 11 | GraphCfg 新增 3 字段 + 2 条校验 | `gnn/msgnn/config.py:50-52,287-290` | ✅ 通过 |
| 12 | 默认 geometry=false，平面路径逐位不变 | `build_graph.py:92-95,126-142`；表达式与求值顺序与改前一致（§5.1） | ✅ 静态成立（未运行，未能实测） |
| 13 | 旧 YAML 不会因新字段报未知键 | `config.py:236-256`；新字段有默认值 | ✅ 通过 |
| 14 | 设计文档“仍缺”五项未被误报为已完成 | 五项均未实现（§6.2） | ✅ 通过（但清单不完整） |
| 15 | 文档称边特征含曲率差 κ1_i−κ1_j | `docs/geometry_representation.md:29` 承诺三项；`build_graph.py:42` 只实现两项 | ❌ 文档与实现不符（S6） |

> 判定图例：✅ 通过；⚠️ 有条件/部分；❌ 不符。

## 3 数学推导（B 的静态依据）

### 3.1 参数化与 frame（F1 的根因）

令 θ=u/R，曲面 r(u,v)=(R sinθ, v, −R(1−cosθ))（`geometry.py:71-79`）：

    r_u  = (cosθ, 0, −sinθ)，‖r_u‖=1
    r_v  = (0, 1, 0)，      ‖r_v‖=1，r_u·r_v=0
    n    = r_u×r_v = (sinθ, 0, cosθ)，‖n‖=1；u=0 时 n=(0,0,1)

所以**行向量** t1=r_u、t2=r_v、n 满足右手系 t1×t2=n、det=+1，且 n 在 u=0 指向 +z（照射/反射侧）。几何本身正确。

但 `geometry.py:93-97` 的赋值把 t1、t2、n 放在矩阵的**行**：

    F = [[ cosθ, 0, −sinθ],
         [ 0,    1,  0   ],
         [ sinθ, 0,  cosθ]]

而 `geometry.py:82` 的 docstring 写的是“columns are t1, t2, n”，并且所有消费者都按**列**取：

- `incidence`：`t1=f[:,:,0]`、`t2=f[:,:,1]`、`nhat=f[:,:,2]`（`geometry.py:130-132`）
- `normals`：`f[:,:,2]`（`geometry.py:100-101`）
- `build_graph`：`frames[src,:,2]`（`gnn/msgnn/data/build_graph.py:151`）

按列读到的是 F 的转置 frame：col0=(cosθ,0,sinθ)、col1=(0,1,0)、col2=(−sinθ,0,cosθ)。它**仍是右手系**（col0×col1=col2），所以只测 `t1×t2=n`、或只测 u=0 的 `n=+z`，都发现不了这个错误；但它不是曲面的切 frame。

数值后果：

- `k_t1 = col0·k = (cosθ,0,sinθ)·(0,0,−1) = −sinθ`；正确值 `r_u·k = +sinθ`。**节点特征 k_t1（0 基索引 10，即第 11 列）反号。**
- `k_t2 = col1·k = 0`，巧合正确。
- `cos_inc = −col2·k = cosθ`，正入射且 k 只有 z 分量时巧合正确；若 k 有 x/y 分量，col2 的 x 分量参与点积，结果会错。
- `normal_z = F[2,2] = cosθ`，行/列两种布局该元素相同，正确（`build_graph.py:137`）。
- `1−n_i·n_j` 用 col2 的点积：col2 是 n 关于 x 的镜像，镜像不改变任意两向量点积，所以数值正确；换成非柱面会错（`build_graph.py:151`）。
- `normals()` 返回 col2=(−sinθ,0,cosθ)，不是 n=(sinθ,0,cosθ)。

**最小修法**：把 `frames()` 改为按列填充（`f[:,:,0]=t1`、`f[:,:,1]=t2`、`f[:,:,2]=n`；plane 单位阵不变），或保留行填充并同步改 docstring、`incidence`、`normals`、`build_graph.py:151`。推荐前者，因为文档和消费者已经按列写。验证必须比较 `frames[:,:,0]` 与 `positions` 对 u 的有限差分（或解析 r_u），不能只测 t1×t2=n 和 u=0。

### 3.2 曲率

单位法向场 n(u,v)=(sinθ,0,cosθ)：

- n_u = (cosθ/R, 0, −sinθ/R) = t1/R，n_v=0；
- 形状算子（约定 S=dn）的特征值为 κ1=1/R（沿 t1）、κ2=0（沿 t2）；
- H=½(κ1+κ2)=1/(2R)，K=κ1κ2=0。

`curvature()`（`geometry.py:107-114`）给的 (1/R, 0, 1/(2R), 0) 正确；符号与“n 朝外、H=½tr(dn)”的约定自洽。若改用教科书常见的 S=−dn，κ1 与 H 会同时变号；当前**没有写明约定**，建议补一句（M1 的修法里一并处理）。曲率是标量，不受 F1 的 frame 布局影响。

### 3.3 面积

‖r_u×r_v‖=‖n‖=1，所以 dA=‖r_u×r_v‖du dv=du dv；`grid_uv` 用等间距 P（`geometry.py:65-69`），故每个单元 A=P² **精确**，单元之间是等距的（无拉伸）。`areas()` 返回 P² 正确（`geometry.py:103-105`），但它与参数化无关地硬编码，见 S2。注意：这里的 P² 是曲面上的物理面元；投影到 xy 的面元是 P²|cosθ|，两者不是同一个量（M2）。

### 3.4 边特征

- 平面：n=(0,0,1)，点积 = 0·0 + 0·0 + 1·1 = 1.0，`mism=0.0` **精确**（`build_graph.py:151`）。
- 平面：`d3 = ‖pos[dst]−pos[src]‖/λ = hypot(Δx,Δy)/λ`；`edge_features` 算的是 `hypot(Δx/λ,Δy/λ)`，数学上同值，浮点上可能差 1 ulp（`build_graph.py:111-113,150`）。
- 柱面：`d3` 对固定 (di,dj,R,P) 是常量（水平 2R sin(P/2R)、垂直 P、对角 sqrt(该值²+P²)）；`mism=1−cos(Δu/R)`，图 radius=1 时只有两个值：垂直 0，水平/对角 1−cos(P/R)（`build_graph.py:149-152`）。两列实质上是“边类型”的类别指示。

### 3.5 incidence 在 u=0

cos_inc=+1 ✅；k_t1=0、k_t2=0。但 u=0 对行/列两种布局完全相同，**这个检查无法发现 F1**；必须测 u≠0（例如用 n_side=3 取 u=−P,0,P，或对 `positions` 做有限差分）。

## 4 问题清单

### 阻断

**F1｜frame 按行填、按列读：柱面 k_t1 反号，normals() 返回镜像法向**

- **file:line**：`gnn/msgnn/data/geometry.py:82`（docstring）、`:93-97`（填充）、`:100-101`（normals）、`:130-132`（incidence）；消费者 `gnn/msgnn/data/build_graph.py:99-104,137,151`（其中 137 的 normal_z 在两种布局下都正确）。
- **依据**：§3.1 的矩阵推导。行向量是正确的切 frame；列向量是转置 frame。`k_t1=col0·k=−sinθ`，正确为 `+sinθ`；`normals()` 返回 (−sinθ,0,cosθ) 而非 n；`cos_inc` 与 `mism` 仅因 k 只有 z 分量、且镜像不改变点积而巧合正确。
- **最小修法**：把 `frames()` 改为按列填充（t1=(cosθ,0,−sinθ) 放 `f[:,:,0]`，t2 放 `f[:,:,1]`，n=(sinθ,0,cosθ) 放 `f[:,:,2]`；plane 单位阵不变）；或保留行填充并同步改 docstring、`incidence`、`normals`、`build_graph.py:151`。推荐前者。
- **验证**：新增测试比较 `frames[:,:,0]` 与 `positions` 对 u 的有限差分/解析 r_u；只测右手性与 u=0 会漏。
- **影响**：`geometry=true` 时 k_t1（0 基索引 10）数值错误；默认 `geometry=false` 与平面阵不受影响，所以是“默认关闭路径的阻断项”。
- **下游影响**：`build_graph.py:158` 存进图字典的 `frame` 同样是行布局；若按 docstring 的“列”使用（例如用 `frame @ v` 做局部→全局变换），会得到转置结果。

### 重要

**M1｜曲面朝向的文档说明与公式相反**

- **file:line**：`gnn/msgnn/data/geometry.py:27-28`。
- **依据**：z(u)=−R(1−cosθ)≤0，u=0 是 z 的最大值（顶点）；n(0)=+z；cos_inc(0)=+1，说明波从 +z 来、照射侧是 +z，曲面朝 **+z** 凸；母圆圆心在 z=−R。原文“bulges towards −z (the illuminated side)”把方向和照射侧都写反了。
- **最小修法**：改为“convex towards +z (the illuminated side); the generating circle is centred at z=−R”。若设计意图是凹面（聚焦），则应把 z 取 +R(1−cosθ) 并同时翻转 n；若实际照射侧确实是 −z，则应改默认 k_hat 与 cos_inc 的符号约定；两种情况都要另加测试，不能只改文字。

**M2｜新增列对当前“平面 / 单一半径柱面 / 正入射”没有独立信息**

- **file:line**：`geometry.py:71-79,103-114,131-132`；`build_graph.py:96-104,137-140,146-152`。
- **依据**：`positions` 给 x=R sinθ（`geometry.py:77-79`），故 x/λ=(R/λ)sinθ；F1 修复后 `k_t1=sinθ=(λ/R)(x/λ)`，是 `x/λ` 列的常数倍（当前是 −(λ/R) 倍）；`cos_inc=cosθ=n_z`，与 `normal_z`（0 基索引 8）**逐位相同**（`build_graph.py:137` 与 `geometry.py:131-132`）；`k_t2=0`、`κ1λ=λ/R`、`κ2λ=0`、`A/P²=1` 全是常量（`geometry.py:103-114`）；边上 `d3` 只依赖 (di,dj,R,P)，`mism` 只有两个值（§3.4）。也就是说 6 列节点特征里 4 列常量、1 列重复、1 列是既有列的缩放；2 列边特征也是边类型常量。
- **最小修法**：在文档中明确这是“多半径/非均匀曲面的接口占位”，当前数据上不增加信息；加一个断言测试（`cos_inc == normal_z`、`k_t1 == ±(λ/R)x_lam`、κ 列常量）。若要真正增加信息，必须引入逐 Case 的几何（`Case` 没有 radius，`dataset.py:114-129`）或自由曲面；对单一均匀柱面（当前 |u|<πR/2 的范围内），任何只依赖 (u,v) 的量都可由 x/y 推出。

**M3｜`geometry=true` + 默认 `surface=plane` 会静默变成 15/7 列且新增列全为常量**

- **file:line**：`config.py:50-51`（默认 false/plane）、`geometry.py:137-141`（geometry=true 就返回 plane Surface）、`build_graph.py:130-152`（追加 6/2 列）。
- **依据**：plane 的 cos_inc=1、k_t1=k_t2=0、κ=0、A/P²=1，边 d3≈r_lam、mism=0；输入从 9/5 变 15/7，Normalizer 长度也变，但与 false **不等价**。最容易踩的路径正是只写 `geometry: true`（surface 默认 plane）。
- **最小修法**：`from_config` 对 plane 返回 None（等价于 false），或在 `_validate` 要求 `geometry ⇒ surface="cylinder"` 并报错；同时把 `surface`/`surface_radius_mm` 在 geometry=false 时标注为无效。

**M4｜几何没有进入物理链路：collate 不带 pos/frame/area/curv，算子仍用平面位置**

- **file:line**：`build_graph.py:221-249`（collate 只带 x/edge_index/edge_attr/q0…；pos 本来就不带，新增的 frame/area/curv 也不带）；`experiment.py:149-155`（算子用 `R.lattice_positions` 平面位置，未传 area）；`radiation.py:57-61,205-213`（相位核用 self.pos_np）。
- **依据**：`geometry=true` 只改网络输入；远场仍是 Σ q_n exp(jk r_n^planar·s)。用曲面 CST 标签训练会与平面算子系统性不一致；`area` 也没有进 `area_mm2`。设计文档 §4 只列了极化与面积，漏了“位置/相位中心”这一项。
- **最小修法**：文档补一条“几何仅进入节点/边特征，辐射层仍按平面位置”；`build_context` 在 `cfg.graph.geometry` 时打印/断言警告；后续把 pos/area/frame 接入 collate 与算子。

**M5｜没有自动化测试；文档把关键自检留到“换机后跑”**

- **file:line**：`gnn/tests/test_graph.py:66-80`（仍断言 9/5）、`:83-88`（只测平面 normal_z）、`:131,150`（硬编码 9/5 建模型）；`docs/geometry_representation.md:62-68`（自检清单）。
- **依据**：没有任何测试 import `geometry`；pytest 全绿也不能证明新路径正确。F1 正是“只测右手性 + u=0”会漏掉的典型。
- **最小修法**：新增 `gnn/tests/test_geometry.py`，至少覆盖：① plane 的 frames=单位阵、curvature=0、positions.z=0；② cylinder 的 `frames[:,:,0]` 与 positions 的 u 导数一致、`frames[:,:,2]`=解析 n、κ1=1/R、H=1/(2R)、K=0；③ u≠0 的 `k_t1=+sin(u/R)`；④ `surface=None` 与 `Surface("plane")` 的前 9/前 5 列逐位相等；⑤ geometry=true 的 x/edge_attr 形状 15/7（edge_features=false 时为 15/0）。

### 建议

**S1｜重复定义未使用的波长常数**：`geometry.py:36-40` 定义 `C0_MM_GHZ`/`lam_mm`，但模块内从未使用（`build_graph` 用 `R.lam_mm`）。删除，或从 `physics.radiation` 导入，避免常数漂移。

**S2｜`areas()` 硬编码 P²**：`geometry.py:103-105` 不随 `kind` 变化；未来若改用投影均匀网格/球面，面积会静默错误。改为由 ‖r_u×r_v‖ 计算，或至少加断言与文档。

**S3｜`build_graph` 不调用 `surface.check()`**：`build_graph.py:121` 接受任意 `Surface`；直接构造 `Surface(kind="cylinder", radius_mm=0)` 会在 `geometry.py:76-79` 除零产生 NaN 而不报错。在 `build_graph` 调用 `check()`，或放进 `Surface.__post_init__`。

**S4｜死代码/死开关**：`from_config` 的 `physics_cfg` 参数未使用（`geometry.py:135`）；`axis` 只在 `check` 里校验、配置没有 `axis` 字段（`:49,57-58`）；`normals()` 未被调用（`:100-101`）。删除或接线。

**S5｜k̂ 固定正入射**：`geometry.py:116` 默认 k_hat=(0,0,−1)，`build_graph.py:135` 不传参；`config.py:56-64` 没有 incident 角度/极化字段。当前所有 k_t/cos_inc 只对正入射有意义；文档写明，或加 `physics.incident_theta_deg/phi_deg` 并传入。

**S6｜文档与实现漂移**：`docs/geometry_representation.md:29` 承诺曲率差边特征，实现只有两列（`build_graph.py:42`）；`:45` 说“不走任何新代码分支”，但 `GraphDataset` 仍调用 `from_config`（`build_graph.py:179`）；`:65` 的 u=0 在偶数 n_side 时不被采样（`grid_uv` 取半整数倍 P，`geometry.py:67-69`），需用 n_side=1 或直接构造；`:67` 的 7 列边特征要求 `edge_features=true`（`build_graph.py:146`）；`docs/gnn_architecture.md:28-29`、`gnn/REPORT.md:134` 仍写 9/5 维而未注明可选 15/7；`geometry.py:2` 的“cylindrical next”已过时；`docs/logs/2026-10-22.md` 无本次记录（`docs/CONVENTIONS.md:39-41`）。

**S7｜几何边特征被绑在 `edge_features_on` 上**：`build_graph.py:146` 的条件是 `surface is not None and edge_features_on`；`edge_features=false, geometry=true` 时 r3d/mismatch 静默丢失，而节点列仍为 15。解耦，或在文档写明。

**S8｜每个 case 重复计算同一套几何**：`build_graph.py:131-135` 对每个 graph 重新调用 positions/frames/areas/curvature/incidence 五个方法（其中 positions、frames、incidence 各自重建 meshgrid，incidence 又调 frames），288 例时是纯重复；可在 `GraphDataset` 算一次并复用（也避免每图重复存 (N,3,3) 的 frame）。

**S9｜没有缠绕角校验**：`geometry.py:55-58` 只要求 R>0；当 R < (n_side−1)P/π 时 θ 可超过 90°（`x=R sinθ` 非单调、cos_inc<0 的节点出现但无标记），更小时会绕柱面多圈。建议校验最大半角 < π/2（至少 < π）并在文档给出有效范围。

**S10｜Normalizer 元数据不含维度**：`normalizer.py:19-25,43-48` 只存 mean/std；旧 9 维 checkpoint 配 `geometry=true` 时会在 `transform_x` 抛 numpy 广播错误而非清晰提示。建议存 `n_x/n_e` 和特征名并显式校验。

## 5 兼容性判断（C/D）

### 5.1 平面路径是否逐位不变

**静态判断：是。** 路径为 `geometry=false` → `from_config` 返回 None（`geometry.py:137-138`）→ `build_graph` 的 `surface is None` 分支（`build_graph.py:126-129`）→ `pos_xy=lattice_xy`（`:127`）→ `node_features(..., geom=None)`。此时 `cols` 的前 9 个元素与改前**逐表达式、逐顺序**相同（`build_graph.py:92-95`），随后同一个 `np.stack(cols, axis=1).astype(np.float32)`（`:105-106`）；边特征仍是同一个 `edge_features` 调用（`:144-145`），几何边块被 `surface is not None` 跳过（`:146`）；`pos` 仍是同一个 `concatenate`（`:128`）。返回字典原有键的值不变，只多三个值为 None 的键（`:158-160`）。

**未能实测**：未运行 Python，因此不能给字节级证据；以上是基于表达式、dtype 和求值顺序的静态结论。新增的 `GraphDataset` 里 `G.from_config(cfg.graph)`（`build_graph.py:179`）在 false 时只是一次返回 None 的调用，无副作用。

### 5.2 返回字典、collate、get、Normalizer

- **collate 安全**：`collate` 只读 x/edge_index/edge_attr/q0/q0_re/q0_im/bits/case_idx/sig_db（`build_graph.py:221-249`），不认识 frame/area/curv，直接忽略；None 值不会进入 batch。
- **get 安全**：`out = dict(g)` 后只对已知键做 tensor 化（`build_graph.py:203-215`）；frame/area/curv 在 geometry=true 时仍是 numpy 数组（不 tensor 化），但当前无消费者；在 false 时是 None。
- **Normalizer 安全**：`fit` 只拼接 x/edge_attr（`build_graph.py:269-270`；`normalizer.py:32-40`），新键不参与。
- **限制**：也正因为 collate 只带 x/edge_attr，frame/area/curv/pos 都到不了模型（M4）；这是“接口已留、链路未接”的状态，不是崩溃。

### 5.3 旧 YAML 与未知键

`_construct` 的未知键检查只针对 dataclass 的字段集合（`config.py:236-240`）；新增的 `geometry/surface/surface_radius_mm` 都有默认值（`:50-52`），旧 YAML 不写它们即可正常加载，不会报 unknown key。`Config.to_dict()` 会把三个新字段写进新配置（`:141-144`），这只会让**旧代码**读新配置时拒绝，属于向前兼容问题，不是本轮的回归。注意：`surface` 的取值校验在 geometry=false 时也会执行（`:287-288`），若旧 YAML 里恰好有非法 surface 会报错，但旧文件没有这个键。

### 5.4 D 的四个隐患

- **encoder 维度自适应**：`Context.node_dim/edge_dim` 直接从 `ds["train"].graphs[0]` 的数组形状取（`experiment.py:54-59`），经 `build_pipeline`（`pipeline.py:167`）到 `GraphNet`/`NodeEncoder`（`residual_gnn.py:43`；`encoders.py:45-48`），没有生产代码硬编码 9/5。只有测试硬编码 9/5（`test_graph.py:131,150`），启用 geometry 的测试需同步改。
- **Normalizer 常量列安全**：`_safe_std` 把 std<1e-8 的列置 1（`normalizer.py:71-74`），常量列 transform 后恒 0，不会 NaN/Inf；plane 的 κ=0、A/P²=1 都属于这种列。注意：若某列在 train 常量、在 val/test 变化，它不会被标准化（std=1），这是既有行为，不是本轮引入。
- **from_config(geometry=true, surface=plane) 不等价于 false**：它返回一个 plane Surface（`geometry.py:137-141`），于是追加 6/2 列常量/重复列，模型输入维度从 9/5 变 15/7，Normalizer 长度也随之变化。见 M3；建议让 plane 直接返回 None。
- **`Optional["G.Surface"]` 无运行期问题**：字符串注解在函数定义时变为 ForwardRef，不求值（`build_graph.py:121`）；`G` 是模块级名字，`typing.get_type_hints` 也能解析。仓库内没有在别的命名空间求值该注解的工具。

## 6 越界与遗漏（A/E）

### 6.1 范围与夹带

- 只改了要求的 3 个源码文件 + 1 个新文档；无重命名、无格式大改、无新第三方依赖、未改默认值。`node_features`/`build_graph` 只加了可选参数，`GraphCfg` 只在末尾追加字段；仓库内没有按位置构造 `GraphCfg` 的调用。
- 轻微多余：`geometry.py:36-40` 的重复波长常数、`:49,57-58` 的 `axis` 死开关、`:100-101` 的 `normals()` 未被调用、`:135` 的 `physics_cfg` 未使用（S1/S4）。没有发现夹带无关行为。

### 6.2 五项“仍缺”是否被误报为已完成

**没有误报；五项确实都还缺。**

1. 辐射层局部极化基：`radiation.py:72-80,201` 仍用全局 (cosθcosφ, −sinφ)，没有按 frame 逐节点投影；
2. 面积进远场求和：`radiation.py:167,192-200` 有 `area_mm2` 钩子，但 `experiment.py:149-155` 不传，`build_graph` 的 `area` 也没接上；
3. 遮挡/背照掩码：`cos_inc` 只是一个特征，没有 backlit/mask，也没有参与 loss/metrics；
4. 单元库角度插值：`config.py:63,366-367` 有 `unit_table`，但 `build_context` 从不加载，`UnitLibrary.from_csv`（`unit_library.py:77`）是死代码，`incidence()` 的输出没有传给库；
5. 非柱面曲面：`check()` 拒绝 plane/cylinder 之外的类型（`geometry.py:51-59`）。

**但“仍缺”清单不完整**，至少漏了：

- 辐射层的相位中心仍是平面位置（M4，`experiment.py:149-155`）；
- 没有可配置的 k̂/极化（S5，`geometry.py:116`）；
- 节点特征没有 z/λ，且 pos/frame/area/curv 不进 batch（M4；对自由曲面这是必要信息）；
- “非柱面…已按此结构预留”偏乐观：`areas()` 硬编码 P²、`axis` 只支持 y（S2/S4），球面不是加一个分支就能正确。

### 6.3 文档准确性（除 M1 外）

- `docs/geometry_representation.md:29` 承诺边特征含“曲率差 κ1_i−κ1_j”，实现没有（`build_graph.py:42`）。
- `docs/geometry_representation.md:45` “`geometry=false` 时不走任何新代码分支”不准确：`GraphDataset` 无条件调用 `from_config`（`build_graph.py:179`），只是返回 None。
- `docs/geometry_representation.md:65` 的 u=0 自检：n_side 为偶数时网格取 u=(k+0.5)P，u=0 不是节点（`geometry.py:67-69`）；要用 n_side=1 或直接构造。
- `docs/geometry_representation.md:67` 的“edge_attr 7 列”只在 `edge_features=true` 时成立（`build_graph.py:146`）。
- `docs/gnn_architecture.md:28-29`、`gnn/REPORT.md:134` 仍写 9/5 维，未注明可选的 15/7；`geometry.py:2` 的“cylindrical next”已过时；`docs/logs/2026-10-22.md` 还没有本次记录（CONVENTIONS §5）。

## 7 是否允许提交

**明确建议：可以有条件提交（commit），但 `geometry=true` 在 F1 修复前不得使用；不得在 M1/M2/M4 的文档澄清前对外宣称“曲面表征已补齐”；按 `docs/CONVENTIONS.md:52-63` 的流程，F1/M5 处理完再 push。**

- **可以提交的理由**：默认 `geometry=false`，平面路径静态逐位不变；配置向后兼容；无新依赖；新模块是默认关闭的骨架，修复面小。
- **必须随提交或紧随修复**：F1（frame 布局，阻断）；M1（朝向文档）；M5（测试）；M3（plane 开关语义）。M2/M4 至少要先在文档里写明“当前列无独立信息、物理层仍平面”。
- **如果本轮的目标是“用 geometry=true 在曲面数据上训练”或“对外交付可用的曲面特征”**：**驳回**——F1 使 k_t1 错误，M2 使新增列无信息增量，M4 使远场仍按平面计算；三者同时成立时，这轮不能称为“补齐曲面表征”。
- 若主 agent 接受以上条件，建议提交信息：`feat(data): 曲面几何表征骨架（默认关闭；平面路径逐位不变）`，并在提交正文注明 F1 修复与新增测试。

## 附录 A 未能确认

- **字节级“逐位不变”未能实测**：本轮不运行代码；§5.1 是表达式/顺序层面的静态结论。
- **CST 曲面按弧长还是按投影 x 布点**：仓库内没有该信息。这决定 `A=P²` 与 `x_lam` 是否符合实际（`geometry.py:65-79,103-105`）；若实际是按投影均匀布点，弧长网格的 P 需要换算。**未能确认。**
- **标签的入射角/极化**：没有找到 `incident_k` 配置或曲面数据；默认 `k_hat=(0,0,−1)` 是否与 CST 激励一致，**未能确认**（`geometry.py:116`）。
- **是否存在曲面数据集及逐 Case 半径元数据**：`Case` 没有 radius 字段（`dataset.py:114-129`），`surface_radius_mm` 是全局配置；数据是否混用多个 R，**未能确认**。
- **`unit_table` 是否计划在本轮接线**：文档 §4.4 说仍缺，代码未接；是否有其它分支/未提交文件在做，**未能确认**。
