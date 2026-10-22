# 编码超表面的物理引导 GNN —— 代码解读

> 面向读者：只系统学过 MLP / CNN，没写过图神经网络（GNN）的人。
> 读完你应该能回答：这个模型输入什么、输出什么、GNN 在哪一步、为什么这么设计、想改哪里该动哪个文件。

---

## 0 先定位：代码到底在哪

你现在打开的工作区 `D:\DSHNESS\GNN` 里是 **CST 建模 / 造数据** 的脚本
（`build_coding_array.py`、`dataset_gen.py`、`postprocess_farfield.py` ……），**没有一行 GNN**。

真正的 GNN 代码在另一个目录：**`D:\GNN\gnn\`**，Python 包名 `msgnn`（v0.1.0）。

```
D:/GNN/gnn/
├─ msgnn/
│  ├─ config.py                配置（dataclass + YAML，未知键直接报错）
│  ├─ experiment.py            总装线：快照 → 样本 → 划分 → 数据集 → 物理算子 → 模型
│  ├─ data/
│  │  ├─ dataset.py            读 CST 的 ff_XXXX.txt / res_XXXX.json，生成 Case、划分
│  │  ├─ build_graph.py        ★ 码 → 图（节点特征、边、批处理、GraphDataset）
│  │  └─ normalizer.py         标准化（只用训练集拟合，防泄漏）
│  ├─ physics/
│  │  ├─ unit_library.py       单元状态 0/1 → 复反射系数 Γ
│  │  ├─ radiation.py          ★ 可微矢量远场算子（torch）：q → E_θ,E_φ → dBsm
│  │  └─ baseline.py           M0 基线 + "全局标量 oracle" 拟合
│  ├─ models/
│  │  ├─ encoders.py           小 MLP 积木（Linear+Act+LN+Dropout）
│  │  ├─ message_passing.py    ★ 手写消息传递（不用 PyG / DGL）
│  │  ├─ residual_gnn.py       ★ M2 / M3 的图网络主体
│  │  ├─ cnn_baseline.py       M1：U-Net 风格 CNN 对照
│  │  └─ pipeline.py           ★ 四种模型的统一封装 + 物理流水线
│  ├─ losses.py                dB 域损失（asinh 压缩）
│  ├─ train.py / evaluate.py / predict.py / inference.py
├─ configs/                    train_m3.yaml / train_m2.yaml / baseline_m1.yaml
├─ scripts/                    make_splits.py / run_baselines.py / smoke_test.py
├─ tests/                      test_radiation.py / test_graph.py / test_dataset.py
└─ README.md / REPORT.md
```

带 ★ 的是必须先读懂的 5 个文件。

---

## 1 这个任务在算什么

### 1.1 物理对象

一块 **20×20 = 400 个单元** 的 1-bit 反射式编码超表面：

| 量 | 值 |
|---|---|
| 单元周期 P | 14 mm（阵列 280 mm ≈ 9.34λ @ 10 GHz） |
| 基板 | ε_r = 2.65，tanδ = 0.0013，厚 1.5 mm，背面 PEC 地板 |
| bit 0 | 圆贴片半径 4.7 mm，Γ₀ = 0.867∠−5.3° |
| bit 1 | 圆贴片半径 2.0 mm，Γ₁ = 0.852∠174.6°（相位差 179.95°） |
| 编码 | 10×10 个"宏比特"，每个宏比特覆盖 2×2 个物理单元（`block=2`） |
| 输出 | 上半球远场，2° 网格：θ 0..90（46 个）× φ 0..358（180 个）= **8280 个方向** |
| 标签 | `σ = |E_θ|² + |E_φ|²`，单位 m²，取 10log₁₀ → **dBsm**（数据集只有幅度，没有相位） |

改变 100 个比特 → 改变 400 个单元的反射相位 → 改变 8280 个方向的散射功率。
传统做法是每个码都跑一次 CST 全波仿真（很慢）；这里想用**一个网络一次前向**预测整张方向图。

### 1.2 关键物理事实（决定了整个架构）

- 如果把每个单元都当成"孤立单元"（局部周期近似），会得到 **M0 基线**：弥散区很准，但**镜面方向差 13.8 dB**（实测 10.80 dBsm，M0 只给 −3.0）。
- 原因：阵列里存在一个与编码近似正交的**均匀共同模** `b`（|b|≈0.37，相位 265°）——可以理解成"整块板子在镜面方向额外相干叠加了一份能量"。
- 结论（来自 `D:/GNN/theory/REPORT.md`）：**局部周期解的结构已经对了，网络只需要学一个小的修正**。这就是 M3 `q = q0 + Δq + b` 的由来。

### 1.3 四个模型（代码里就是 `model.name` 四个取值）

| 编号 | 定义 | 输出 | 参数量 | 作用 |
|---|---|---|---|---|
| **M0** | `q = q0`（查单元库），直接过物理算子 | dBsm | **0** | 物理基线，不训练 |
| **M1** | 20×20 比特图 → U-Net → 46×180 dB 图 | dBsm | ≈212k | **无物理、无图**的对照（相当于你熟悉的 CNN 回归） |
| **M2** | `q = GNN(图)`，不加 q0 | dBsm | ≈97k | 消融：残差（skip）到底值不值 |
| **M3** | `q = q0 + Δq(GNN) + b(全局)` | dBsm | ≈101k | **主模型** |

M0g 不是模型，是"给 M0 每样本拟合 1 个复标量"的 **oracle**（用了标签），只作为上界参考。

---

## 2 从 MLP / CNN 到 GNN：只需要三个类比

### 2.1 一句话

> **CNN 是"规则网格上的局部加权求和"，GNN 是"任意图上、用一个小 MLP 代替卷积核的局部求和"。**

把 3×3 卷积写成 GNN 的语言：

```
卷积：  y[i] = Σ_{j∈N(i)} W[offset(i,j)] · x[j]
GNN：   y[i] = Σ_{j∈N(i)} MLP([x[j], x[i], e_ij])      ← 权重不是一个矩阵，而是一个小网络
```

区别只有两点：

1. **邻居由 `edge_index` 给出**，不再假设"上下左右"，所以能处理非规则阵列、曲面、缺单元；
2. **卷积核的"位置"变成了边特征** `e_ij`（相对位移），网络自己决定"往这个方向传多少"。

在这份代码里，图恰好是 20×20 的规则网格（8 邻域），所以它和 3×3 卷积的感受野**完全一样**——GNN 在这里的价值不是"能处理不规则"，而是：**节点 = 单元、边 = 耦合，物理含义清晰，且天然支持以后换成曲面/共形阵**。

### 2.2 对照表

| | MLP | CNN（M1） | 本项目的 GNN（M2/M3） |
|---|---|---|---|
| 输入 | 一个向量 | 一张图 (C,H,W) | 一张图：400 节点 × 9 特征 + 2964 条边 × 5 特征 |
| 局部性 | 无（全连接） | 3×3 窗口 | 8 邻域（`graph.radius=1`） |
| 权重共享 | 无 | 卷积核在空间上共享 | `MLP_msg` / `MLP_upd` 在所有节点、所有边上共享 |
| 位置信息 | 无 | 隐含在网格索引 | **显式**：节点带 x/λ、y/λ，边带 Δx/λ、Δy/λ、r/λ |
| 等变性 | 无（要对齐） | 平移等变 | **排列（节点重排）等变** |
| 输出 | 向量 | 一张图 (46,180) | 每个节点 2 个数（复权重的实部/虚部）→ 再经物理层变 8280 个方向 |
| 典型病 | 参数多 | 需要规则网格 | 深层**过平滑**（这里只有 3 层，且有残差+LayerNorm） |

### 2.3 这张"图"具体长什么样

```
节点：400 个（= 20×20 单元），每个节点 9 维特征
边  ：每格连上下左右 + 4 个对角 = 8 条出边，双向都存 → 2964 条有向边
      角落节点只有 3 个邻居，边上节点 5 个，内部 8 个（不做周期延拓）
```

2964 怎么来的：水平方向 19×20×2 = 760，垂直方向 760，四个对角方向各 19×19 = 361（共 1444）
→ 760 + 760 + 1444 = 2964。（`tests/test_graph.py::test_edge_index_radius1` 就是在钉这个数。）

---

## 3 全景：一次前向传播到底发生了什么

```
10×10 码（100 bit）
      │  np.repeat 2×2  （block=2）
      ▼
20×20 物理比特（400 单元）
      │  查表 Γ(bit)                    ← physics/unit_library.py
      ▼
每单元 q0 ∈ ℂ（0.867∠−5.3° 或 0.852∠174.6°）
      │
      ├──────────────► 建图 G：x(400,9)、edge_index(2,2964)、edge_attr(2964,5)
      │                        │
      │                        ▼
      │                 GNN: node_enc → 3×消息传递 → head
      │                        │            └─ mean-pool → MLP → b
      │                        ▼
      │                  Δq ∈ ℂ⁴⁰⁰（实部/虚部各 400）
      ▼                        ▼
   q = q0 + Δq + b        ← M3（M2 只有 Δq，M0 只有 q0）
      │
      ▼  固定、不可学习、但可微的衍射积分   ← physics/radiation.py
   S(θ,φ) = Σₙ qₙ · exp[ j k (xₙu + yₙv + zₙw) ]      8280 个方向
      │
      ▼
   E_θ = C·cosθcosφ·S ,   E_φ = −C·sinφ·S ,   C = 2√π/λ · P² · 10⁻³
      │
      ▼
   σ = |E_θ|² + |E_φ|²  →  10log₁₀  →  dBsm (8280,)
      │
      ▼  与 CST 标签比：asinh 压缩后的 dB MSE       ← losses.py
```

**最反直觉、也最重要的一点**：网络**不直接输出 8280 个 dB 值**，它只输出 **400 个复数（800 个实数）**，
剩下的 8280 个方向由一段写死的物理公式算出来。这就是"物理引导"（physics-informed）的全部含义。

好处：

1. 学习目标从 8280 维降到 800 维，参数/数据效率高得多；
2. 远场的"干涉结构"由算子精确给出，网络不需要从零学"波怎么传播"；
3. 算子可微 → 梯度能穿过它回传到 GNN → 以后可以直接做**反设计**（对 q 求梯度来优化编码）。

### 3.1 张量形状（batch = 8 时）

| 张量 | 形状 | 含义 |
|---|---|---|
| `x` | (3200, 9) | 8 个图 × 400 节点，拼接 |
| `edge_index` | (2, 23712) | 8 × 2964，索引已按图偏移（图 1 从 400 开始……） |
| `edge_attr` | (23712, 5) | 边特征 |
| `batch` | (3200,) | 每个节点属于第几个图（0..7） |
| `ptr` | (9,) | `[0, 400, 800, …, 3200]`，快速切片 |
| `q0` | (3200,) complex | 每节点基线权重 |
| `sig_db` | (8, 8280) | 标签 |
| GNN 中间层 `h` | (3200, 64) | 每节点 64 维嵌入 |
| 算子输出 | (8, 8280) × 4 | E_θ/E_φ 的实部/虚部 |

---

## 4 数据层

### 4.1 `data/dataset.py` —— 把 CST 文件变成样本

读两样东西：

```
results/ff/ff_XXXX.txt     8280 行 × 4 列：theta phi |E_theta|_dBsm |E_phi|_dBsm   （只有幅度）
results/res_XXXX.json      code(100 字符), specular_dbsm, mean_far_dbsm, max_dbsm, seed, block
```

核心函数：

- `Grid.from_step(2.0)`：生成 46×180 的固定角度网格（`theta` 外层，和 CST 导出一致）。
- `case_from_files()`：把 100 字符的码 reshape 成 10×10，再按 `block=2` 复制成 20×20 的 `bits`。
- `load_target()`：`|E| = 10^(dB/20)`，`σ = |E_θ|²+|E_φ|²`，再 `10log10` 回 dBsm。**这一步是"把幅度变成功率"，别小看它——模型比的是功率不是幅度。**
- `scan_cases()`：只接受"ff 文件 + res json 都在、行数/角度网格对得上"的样本（json 是生成器最后写的，所以它存在 = 样本完整）。
- `build_snapshot()`：给每个 ff 文件记 size + sha256，冻结成 `snapshot.json`。
  **训练期间 CST 新生成的样本不会偷偷溜进来**（否则 M0 和 M3 就不是同一批数据了）。
- `make_splits()`：按 `layout_id` 分组 70/15/15，并自检"同一组不跨 split、并集等于全集"。

> 为什么要"快照 + 分组"？这是深度学习里最容易翻车的地方：数据一边生成一边训练，测试集泄漏了你还不知道。这里用三重保险（快照、分组划分、normalizer 只在训练集上拟合）把口子堵死。

### 4.2 `data/build_graph.py` —— 本文档的重点之一

#### （1）节点特征：9 维

```python
NODE_FEATURES = ("bit", "bit_signed", "x_lam", "y_lam", "gamma_re", "gamma_im",
                 "gamma_abs", "boundary", "normal_z")
```

| # | 名称 | 含义 | 为什么要它 |
|---|---|---|---|
| 0 | `bit` | 0/1 编码 | 最原始的信息 |
| 1 | `bit_signed` | 2·bit−1 → ±1 | 让一个线性层就能把两种状态分开（0/1 不对称） |
| 2,3 | `x_lam`, `y_lam` | 单元位置 ÷ λ | **绝对位置**。没有它，网络不知道"这个单元在阵列哪" |
| 4,5,6 | `gamma_re/im/abs` | 该单元的复反射系数 | 物理单位；其实和 bit 一一对应（两个常数之一），但网络更容易用 |
| 7 | `boundary` | 边缘为 1 | 边缘单元邻居少、截断效应强 |
| 8 | `normal_z` | n̂·ẑ（平面阵恒 1） | 给**曲面/共形阵**留的接口 |

代码（`build_graph.py:76`）：

```python
x = np.stack([b, 2.0*b-1.0,
              pos_xy[:,0]/lam, pos_xy[:,1]/lam,
              g.real, g.imag, np.abs(g),
              boundary.astype(np.float64), nz], axis=1)
```

> 注意：位置是**显式输入**的。所以这其实不是"纯拓扑 GNN"，而是带**绝对位置编码**的图网络——否则平移一下阵列，输出就变了。

#### （2）边：8 邻域 + 5 维边特征

```python
def neighbour_offsets(radius, self_loops=False):
    for di in range(-radius, radius+1):
        for dj in range(-radius, radius+1):
            if di == 0 and dj == 0 and not self_loops: continue
            out.append((di, dj))
```

`radius=1` → 8 个偏移；`radius=2` → 24 个（多一圈"长程"耦合，配置里可改）。

```python
def edge_features(edge_index, pos_xy, lam):
    dx = (pos_xy[dst,0] - pos_xy[src,0]) / lam
    dy = (pos_xy[dst,1] - pos_xy[src,1]) / lam
    r  = np.hypot(dx, dy)
    az = np.arctan2(dy, dx)
    return np.stack([dx, dy, r, np.cos(az), np.sin(az)], axis=1)
```

边特征 = 相对位移（单位 λ）+ 距离 + 方位角的正余弦。
用 `cos/sin` 而不是角度本身，是为了避免 ±180° 的跳变。

**双向边**：`edge_index` 里 (i→j) 和 (j→i) 都存。因为消息函数看到的是 `[h_i, h_j, e_ij]`，顺序不同结果就不同，必须分开。

`edge_index_grid()` 里先按 `(source, target)` 排序（`np.lexsort`），保证**每次运行边的顺序完全一致**（可复现）。

#### （3）打包成图字典

```python
return {"x": x, "edge_index": ei, "edge_attr": ea, "pos": pos,
        "q0": gamma, "q0_re": ..., "q0_im": ..., "bits": ..., "n_nodes": 400, "n_edges": 2964, ...}
```

#### （4）`collate()`：不用 PyG 的批处理

把 8 张独立的图拼成一张"大图"，但**图与图之间没有边**：

```python
eis.append(ei + ptr[-1])                      # 索引整体平移
batches.append(torch.full((n,), k))           # 记录每个节点属于第几张图
ptr.append(ptr[-1] + n)                       # [0, 400, 800, ...]
```

这样一次前向就能算完 8 个样本，而 `index_add_` 只在各自图内聚合，**不会串味**。
（`tests/test_graph.py::test_collate_keeps_graphs_apart` 就是在验证这个。）

> `pos`（节点坐标）**没有**进 batch。因为所有样本共享同一套 20×20 栅格，物理算子自己存了一份相位核，不需要每个样本再传一遍。

### 4.3 `data/normalizer.py` —— 标准化

只用**训练集**的图算 mean/std，把 9 维节点特征和 5 维边特征各自标准化，存成 `normalizer.json`。

细节：`_safe_std()` 把方差为 0 的列（比如平面阵的 `normal_z` 恒为 1）的 std 强行设成 1，避免除零。

`bit` 这一列标准化后是 ±1 左右（均值 0.5、std 0.5），`boundary` 大约 −0.5/+2，量级就统一了。

---

## 5 物理层：三段不训练、但很关键的代码

### 5.1 `physics/unit_library.py` —— 查表得到 Γ

```python
GAMMA_ABS   = (0.867, 0.852)     # |Γ| for bit 0 / bit 1
GAMMA_PH_DEG = (-5.3, 174.6)     # 相位（度）
```

`library(bits)` 就是一个花式索引：`self.gamma[state]`。
`gamma_source="unit"` 时把 |Γ| 改成 1（用来验证"−1.24 dB 是 CST 数值损耗"这个假设）。

还留了 `from_csv()`：读 `state,theta,phi,re,im` 表做双线性插值，为将来的**斜入射**扩展。

### 5.2 `physics/radiation.py` —— 可微远场算子（**全文最漂亮的 30 行**）

物理公式（和 `D:/GNN/theory/` 里完全一致）：

```
S(θ,φ) = Σₙ qₙ · exp[ j k (xₙ·u + yₙ·v + zₙ·w) ]        (u,v,w) 是单位方向矢量
E_θ = C · cosθ·cosφ · S
E_φ = −C · sinφ · S
σ   = |E_θ|² + |E_φ|²                                    [m²]，dBsm = 10log₁₀σ
C   = 2√π/λ · P² · 10⁻³
```

这就是"每个单元的贡献乘以一个相位，然后全阵列求和"——**离散化的衍射积分**。
写成矩阵就是 `S = q @ K`，其中 `K[m,n] = exp(jk r_n·ŝ_m)` 是 (8280, 400) 的复矩阵，**与 q 无关、可以预计算**。

因为 PyTorch 对复数 autograd 的约定容易踩坑，作者把复数拆成实部/虚部，用两次实数矩阵乘实现（`radiation.py:245`）：

```python
s_re = (q_re @ kc.t() - q_im @ ks.t()) * c     # kc = cos(k r·s), ks = sin(k r·s)
s_im = (q_re @ ks.t() + q_im @ kc.t()) * c
```

再乘极化投影：

```python
outs["eth_re"].append(s_re * pth)   # pth = cosθcosφ
outs["eph_re"].append(s_re * pph)   # pph = −sinφ
```

**自检（每个模型都必须过的一关）**：如果 `qₙ ≡ 1`（全 1 口径，等效于一块 PEC 平板），
则 θ=0 时 `σ = 4πA²/λ² = 19.342 dBsm`。这一条同时钉死了单位、面积、常数、角度网格和极化约定。

> 为什么默认 `projection="vector"` 而不是更简单的 `scalar`（只有 cosθ）？因为实测 E 面和 H 面差 −1.84 dB，矢量投影预测 −1.61 dB，标量投影预测 0 dB。矢量形式才和全波数据对得上。

### 5.3 `physics/baseline.py` —— M0 与 oracle

- `q0_from_bits()`：比特 → q0。
- `baseline_sigma_db()`：q0 → 远场 → dBsm。**零参数**。
- `fit_global_scalar()`：给定一条实测曲线，拟合一个复标量 `b`，使 `|g0 + b·gu|²` 最接近标签。
  用**极坐标粗搜索 + 2 维 Adam**（只有 2 个实参数，不需要复杂优化器）。
  这是 M0g oracle，只用于回答"1 个复标量能解释多少缺口"，**不能当预测模型**（它用了标签）。

---

## 6 模型层

### 6.1 `models/encoders.py` —— 就是 MLP 积木

```python
class MLP(nn.Module):
    """dims[0] → dims[1] → ... → dims[-1]；每个隐藏层后接 act + dropout"""
```

`ACTS = {"relu", "gelu", "silu", "tanh"}`。
`NodeEncoder` / `EdgeEncoder` 只是"输入维度 → hidden → hidden"两层的特例。

这部分你完全熟悉，跳过。

### 6.2 `models/message_passing.py` —— GNN 的核心，65 行

#### 三个公式

```
① 消息：  m_ij = MLP_msg( [ h_i , h_j , e_ij ] )        i = 源(邻居)，j = 目标(自己)
② 聚合：  agg_j = Σ_{i→j} m_ij                          （或 mean）
③ 更新：  h'_j = LayerNorm( h_j + Dropout(act(MLP_upd([h_j, agg_j]))) )
```

#### 逐行

```python
msg_in = 2 * hidden + max(edge_dim, 0)          # 64+64+64 = 192
self.msg = MLP([msg_in, hidden, hidden])        # 192 → 64 → 64
self.upd = MLP([2*hidden, hidden, hidden])      # 128 → 64 → 64
self.norm = nn.LayerNorm(hidden)
```

```python
src, dst = edge_index[0], edge_index[1]
parts = [h[src], h[dst]]                        # 每条边取两端特征
if edge_attr is not None ...: parts.append(edge_attr)
m = self.msg(torch.cat(parts, dim=-1))          # (E, 64)  每条边一条消息
agg = h.new_zeros(h.shape)
agg.index_add_(0, dst, m)                       # ★ scatter-add：按目标节点求和
if self.aggr == "mean":
    deg = torch.bincount(dst, minlength=h.shape[0]).clamp_min(1)
    agg = agg / deg.to(h.dtype).unsqueeze(1)
out = self.upd(torch.cat([h, agg], dim=-1))
h = h + self.drop(self.act(out))                # 残差
h = self.norm(h)                                # 逐节点 LayerNorm
```

**`index_add_` 是整段代码的心脏**。它做的事：

```
给定 m = [m0, m1, m2, m3]，dst = [1, 1, 3, 1]
agg[1] = m0 + m1 + m3
agg[3] = m2
agg[0] = agg[2] = 0
```

也就是"把所有指向节点 j 的消息加起来"。这正是"聚合"这一步，而且它是**可微**的（反向就是按索引把梯度分发回去），所以能端到端训练。

**为什么用 `sum` 而不是 `mean`？** 默认 `aggr="sum"`。sum 保留了"邻居数量"这个信息（角上 3 个邻居 vs 中间 8 个邻居，耦合总量本来就不同）；mean 则把度数归一化掉。两种都是排列等变的。想切换得改 `pipeline.py` 里 `GraphNet(..., aggr=...)`——目前没暴露到 YAML。

**为什么用 LayerNorm 而不是 BatchNorm？** BatchNorm 统计的是"同一个通道在 batch 上的均值方差"，而这里是"每个节点自己 64 维的归一化"。图的大小、节点数在 batch 里不一致时，BatchNorm 会很别扭；LayerNorm 对每个节点独立，天然适配。

**残差 `h + ...`**：让 3 层堆叠时梯度能直通，也缓解 GNN 的"过平滑"（层数多了所有节点表示趋同）。

#### 一层消息传递的手算例子

4 个节点排成一条线 1—2—3—4，`h = [h1,h2,h3,h4]`：

```
指向 2 的边：(1→2), (3→2)
m_{1→2} = MLP_msg([h1, h2, e12])
m_{3→2} = MLP_msg([h3, h2, e32])
agg_2   = m_{1→2} + m_{3→2}
h2'     = LN( h2 + GELU( MLP_upd([h2, agg_2]) ) )
```

3 层之后，每个节点"看到"半径 3 格以内的信息（约 3×14 mm = 42 mm ≈ 1.4λ）。

#### `MessagePassingStack`

就是 `for layer in self.layers: h = layer(h, edge_index, edge_attr)`，层与层之间共享同一个 `edge_index` 和边嵌入。

### 6.3 `models/residual_gnn.py` —— 图网络主体

```python
class GraphNet(nn.Module):
    node_enc  : 9  → 64 → 64          # 节点特征升维
    edge_enc  : 5  → 64 → 64          # 边特征升维（一次，所有层共用）
    mp        : 3 × MessagePassingLayer(64, 64)
    head      : Linear(64 → 2)        # 每节点输出 (Δq 实部, Δq 虚部)
    glob      : MLP(64 → 64 → 2)      # 全局支路：整图池化 → b 的实部/虚部
```

前向（`forward`）：

```python
h = self.node_enc(x)                  # (N, 9) → (N, 64)
e = self.edge_enc(edge_attr)          # (E, 5) → (E, 64)
h = self.mp(h, edge_index, e)         # 3 层消息传递
out = self.head(h)                    # (N, 2)
d = {"node_re": out[:,0], "node_im": out[:,1]}

# 全局支路：对每张图做 mean pooling，再 MLP
g = self.glob(self._pool(h, batch["batch"], n_graphs))   # (B, 2)
d["glob_re"], d["glob_im"] = g[:,0], g[:,1]
```

池化：

```python
pooled = h.new_zeros((n_graphs, 64))
pooled.index_add_(0, batch, h)        # 同图的节点加起来
cnt = torch.bincount(batch).clamp_min(1)
return pooled / cnt                   # 除以节点数 = mean pooling
```

#### 零初始化输出头（非常重要的设计）

```python
if zero_init_head and not direct:
    nn.init.zeros_(self.head.weight); nn.init.zeros_(self.head.bias)
    nn.init.zeros_(last.weight);     nn.init.zeros_(last.bias)   # glob 的最后一层
```

效果：

- 初始化时 `Δq ≡ 0`、`b ≡ 0` → **M3 恰好等于 M0**。
- 于是"第 0 个 epoch = 物理基线"，之后涨的每一分都是学出来的，不存在"初始化就比基线好/差"的混淆。
- 一个细节：`head.weight = 0` 意味着第一步 `∂L/∂h = 0`，所以**第一步只更新 head 和 glob**，第二步起消息传递才开始拿到梯度。这正好符合"先学全局偏置，再学局部修正"的直觉。

### 6.4 `models/pipeline.py` —— 四种模型的统一封装

```python
def q_of(self, batch):
    if self.kind == "m0":  return q0_re, q0_im
    out = self.net(batch)
    if self.kind == "m2":  return out["node_re"], out["node_im"]
    # M3：先去掉 Δq 的图内均值，再加 q0 和全局 b
    n_re, n_im = _remove_graph_mean(out["node_re"], out["node_im"],
                                    batch["batch"], n_graphs)
    q_re = q0_re + n_re + out["glob_re"][batch["batch"]]
    q_im = q0_im + n_im + out["glob_im"][batch["batch"]]
    return q_re, q_im
```

`_remove_graph_mean()` 是后来审计加的（代码注释里叫 B3）：**b 和 mean(Δq) 不可辨识**——一个常数偏置放在哪里数学上等价。强制 `mean(Δq)=0` 之后，均匀分量只能由 b 承担，`|b|` 才保持"≈0.37"的物理含义。

`forward()` 负责把 (B·N,) 摊平的 q 变回 (B, N)，再调用算子；如果 batch 里图大小不一，就逐图算再拼（当前全是 20×20，走的是快路径）。

`build_net()` 根据 `cfg.model.name` 造模型；`build_pipeline()` 把模型和算子包在一起。

### 6.5 `models/cnn_baseline.py` —— M1，你熟悉的那种 CNN

```
20×20 bits → 补零到 32×32 → 编码器 (32/16/8/4) → 解码器（带 skip 连接）
           → 1×1 卷积到 rank=4 通道 → 因子化读出 A[46,32] · f · B[180,32]ᵀ
           → + 可学习的"天空"偏置 sky → 46×180 dB 图
```

要点：

- 它不是简单 CNN，是 **U-Net**（编码-解码 + skip），因为输出是"图和输入不同分辨率"。
- **因子化读出**：不用 8280 维的全连接（那要 8280×256 ≈ 2M 参数），而用 `A(46×32) @ G(32×32) @ B(32×180)`，参数少 8 倍，还自带"平滑方向图"的先验。
- 参数量 ≈212k，比 GNN 大一倍。
- 它**没有物理、没有图、没有单元库**——是"纯数据驱动"的对照组，用来证明物理先验的价值。

---

## 7 损失与训练

### 7.1 损失（`losses.py`）

```python
delta = (pred_db - targ_db).clamp(-80, 80)      # 截断，防爆
g     = c * asinh(delta / c)                    # 动态范围压缩，c = 3 dB
loss  = Σ_m w_m · g² / (B · Σ_m w_m)
```

**为什么要 asinh 压缩？** 镜面瓣 10.8 dBsm，弥散区 −6.6 dBsm，最深处差 25–30 dB。
如果直接 MSE，40 dB 的误差会贡献 1600，梯度几乎全被镜面点吃掉，弥散结构学不动。

`asinh` 的性质：

| 误差 | asinh 后 | 平方 | 对比 MSE |
|---|---|---|---|
| 1 dB | 0.98 | 0.96 | 1（几乎一样） |
| 40 dB | 9.80 | 96 | 1600（**抑制 16 倍**） |

即"小误差照常按 dB 算，大误差按对数算"。`compression: none` 可退回纯 MSE。

**角度权重**：

```python
w = sin(θ) + 0.2                    # 立体角权重 + floor（sin0=0 会把镜面点权重抹成 0）
w *= 3.0 if θ < 6°                  # 主瓣额外加权
w /= w.mean()
```

为什么要 `sin(θ)`：θ 均匀采样时，极区附近每个环的立体角小，不加权就重复计数了。

### 7.2 训练循环（`train.py`）

```python
opt   = AdamW(lr=1e-3, weight_decay=1e-4)
sched = CosineAnnealingLR(T_max=epochs, eta_min=1e-5)
for epoch in range(1, 61):
    for batch in shuffle(train):
        out = model(batch)
        loss = crit(out["sig_db"], batch["sig_db"])
        loss.backward()
        clip_grad_norm_(1.0)
        opt.step()
    # 验证：只用 val，早停 patience=15，best.pt 按 val_loss 选
```

一次训练写出来的文件：

```
config.yaml       完全解析后的配置（可复现）
snapshot.json     冻结的文件清单
splits.json       实际用的划分
normalizer.json   训练集特征统计
best.pt/last.pt   权重
history.csv       每 epoch 的 loss/rmse/bias/rho
summary.json      最佳 epoch、参数量、耗时
```

> **test split 只在 `evaluate.py` 里被碰**。训练、早停、选模型都只看 val。这是"不偷看考卷"的纪律。

---

## 8 评估与推理

### 8.1 指标（`evaluate.py`）

单个相关系数会选错模型（镜面瓣主导方差），所以用固定三件套：

| 指标 | 定义 | 回答什么 |
|---|---|---|
| `rho_lin` | θ∈[0,90] 上**线性功率**的 Pearson r | 镜面 13.8 dB 的缺口补上没 |
| `rho_db` | θ∈[6,90] 且实测 > −30 dBsm 上 **dB 值**的 r | 弥散结构/零深对不对 |
| `bias_db` | 同一集合上 mean(pred − meas) | 能不能当绝对电平预测器（\|bias\|≤3 dB 才算数） |
| `rmse_db` | 同一集合 RMS | 综合 |
| `spec_err` | θ=0 处的差 | 镜面 |
| `mean_far_err` | θ∈[10,90] 线性均值之差 | 弥散电平 |
| 分带 | 0–5 / 5–15 / 15–30 / 30–60 / 60–90° | 误差集中在哪个角域 |

### 8.2 推理（`predict.py`）

跑一个样本，把 `θ, φ, E_θ, E_φ, σ_dB, 标签, q, q0` 存成 `.npz`，并打印：

```
specular: model X.XX dBsm | measured Y.YY dBsm
mean far: ...
q: |q0| mean 0.860 | |dq| mean 0.0xx | mean(dq) ...
```

`|dq|` 的大小告诉你"逐单元修正有多强"，`|b|` 告诉你"全局共同模学到了多少"（对照理论值 0.37）。

---

## 9 为什么这么设计：8 个决策

| # | 决策 | 理由 |
|---|---|---|
| 1 | 网络只输出 q（400 复），不输出 8280 个 dB | 学习目标从 8280 维降到 800 维；远场干涉由物理精确给出 |
| 2 | M3 用 `q0 + Δq + b` 残差形式 | 局部周期解结构已对，只学小修正 → 数据效率高 |
| 3 | 零初始化 head | 初始 = M0，改进可归因 |
| 4 | 全局支路（1 个复标量/样本） | 物理上最大的误差源就是那个均匀共同模，2 个实自由度就能拿走大部分增益 |
| 5 | 图只连 8 邻域（3 层 → 1.4λ） | GNN 只管**局部耦合修正**；长程干涉交给算子，不需要大感受野 |
| 6 | 手写消息传递，不用 PyG/DGL | 依赖少、可读、批处理逻辑透明（约 65 行） |
| 7 | dB 域 + asinh 压缩 + sinθ 权重 | 处置 25–30 dB 的动态范围 |
| 8 | 快照 / 分组划分 / 训练集 normalizer | 防数据泄漏，保证 M0 与 M3 可比 |

---

## 10 常见疑问 Q&A

**Q1：400 个节点，可码只有 100 个比特，是不是浪费？**
不是。码控制 2×2 的"宏比特"（工艺上便于布线），但每个物理单元的位置、边界、以及阵列中的耦合都不同。GNN 输出的 Δq 是**逐单元**的，它可以把同一宏比特里的 4 个单元微调得不一样。

**Q2：这就是 GCN 吗？**
不是。GCN 是 `h' = σ(D^{-1/2}AD^{-1/2} h W)`，聚合是**固定权重**的线性加权。这里每条边的消息是 `MLP([h_i,h_j,e_ij])`，是**边条件卷积（edge-conditioned conv）**，表达力更强，而且能吃边特征。

**Q3：为什么不用注意力（GAT）？**
可以，但这里的边是规则栅格、边特征已经显式给了几何，注意力带来的额外自由度在 240 个样本上大概率先过拟合。先用最简单的。

**Q4：3 层够吗？会不会感受野太小？**
"局部耦合"这件事的物理尺度就是 1–2 个单元（λ/2 量级），3 格 ≈1.4λ 够了。真正的长程效应（整孔径相干叠加）被算子精确处理了，不需要 GNN 学。
如果以后要做"跨单元的长程耦合"（比如表面波），把 `graph.radius` 改成 2（24 邻域）或多尺度边即可。

**Q5：为什么 LayerNorm 加在残差之后？**
写法是 `h ← LN(h + f(h))`（先残差相加、再归一化，属于 post-norm 那一类）：归一化保证每层输出的尺度稳定，3 层堆叠不容易数值爆炸。代价是 `h` 的尺度每层被重置，但这里每层都重新加了残差，所以不会丢信息；最后 head 看到的就是归一化后的表示。

**Q6：图是规则的，那 CNN 不是更简单？**
对平面 20×20 阵，CNN（M1）确实能跑，而且它就是对照组。选图的理由是：(a) 节点/边的物理含义直接对应"单元/耦合"；(b) 换曲面、共形、缺单元阵列时不用改代码；(c) 输出天然是"每单元一个量"，不用把 400 个单元摊平成图像再摊回来。

**Q7：训练时 8 个图拼在一起，消息会不会串？**
不会。`collate` 把 `edge_index` 整体平移，边只指向自己图内的节点；`index_add_` 按目标节点累加，天然隔离。有测试钉住。

**Q8：为什么损失在 dB 域而不是线性功率域？**
线性域里镜面点比弥散点大 3 个数量级，MSE 会只盯镜面。dB 域 + asinh 让每个角域都有话语权。但**指标**里同时保留了 `rho_lin`（线性域相关），因为"镜面补没补上"必须在线性域看。

**Q9：b 和 Δq 是不是重复了？**
数学上会重复（常数偏置放哪都行），所以代码里强制 `mean(Δq)=0`（`_remove_graph_mean`），让 b 独占均匀分量。这样 `|b|` 才有物理意义。

**Q10：为什么不用复数张量？**
PyTorch 的复数 autograd 对共轭、`view`、`index_add_` 的支持历史上坑很多。拆成实部/虚部，所有运算都是普通实数运算，行为完全可预期。

---

## 11 怎么运行

```bash
cd D:/GNN/gnn

# 依赖（CPU 版 torch 足够）
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install pyyaml numpy scipy pytest

# 1) 单元测试（含 19.342 dBsm 自检、torch/numpy 对齐、排列等变）
pytest tests/ -q

# 2) 冒烟：8 例 2 epoch，< 5 min，末行 SMOKE PASS
python scripts/smoke_test.py

# 3) 冻结文件清单 + 划分
python scripts/make_splits.py --out runs/splits.json

# 4) 训练 M3 / M2 / M1
python -m msgnn.train --config configs/train_m3.yaml --seed 0 \
    --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_s0
python -m msgnn.train --config configs/train_m2.yaml --seed 0 ... --out runs/m2_s0
python -m msgnn.train --config configs/baseline_m1.yaml --seed 0 ... --out runs/m1_s0

# 5) 评估（M0/M0g 和其它 run 放一起，保证同一快照同一 split）
python -m msgnn.evaluate --runs runs/m3_s0 runs/m2_s0 runs/m1_s0 m0 m0g \
    --out runs --splits val,test

# 6) 单例诊断
python -m msgnn.predict --run runs/m3_s0 --case 0 --out runs/m3_s0/pred_0000.npz
```

### 想改点什么，去哪改

| 想做的事 | 改哪里 |
|---|---|
| 隐藏维度 / 层数 | `configs/*.yaml` → `model.hidden` / `model.n_layers` |
| 更大邻域（长程耦合） | `graph.radius: 2`（24 邻域，边数 400→~9000） |
| 去掉全局支路（消融） | `model.global_branch: false` |
| 换成"直接预测 q"的 M2 | `model.name: m2` |
| 关掉压缩 / 改主瓣权重 | `loss.compression: none` / `loss.mainlobe_boost` |
| 用 |Γ|=1 的库 | `physics.gamma_source: unit` |
| 标量极化 | `physics.projection: scalar` |
| 换聚合方式（sum→mean） | 代码：`models/pipeline.py` 的 `GraphNet(..., aggr="mean")`（未暴露到 YAML） |
| 加节点/边特征 | `data/build_graph.py` 的 `NODE_FEATURES` / `node_features()` / `edge_features()` |

> 注意：加了特征一定要同步 `NODE_FEATURES` 元组（它只是文档性的，但保持同步），并且 `tests/test_graph.py` 里断言 `(400, 9)` / `(2964, 5)` 的地方要跟着改。

---

## 12 建议的阅读顺序

1. **`configs/train_m3.yaml`**（47 行）——先知道有哪些旋钮。
2. **`data/build_graph.py`** ——搞清楚"样本长什么样"。
3. **`models/message_passing.py`**（65 行）——GNN 的全部魔法就在这里。
4. **`models/residual_gnn.py`** ——它怎么被用起来。
5. **`models/pipeline.py`** ——q 怎么合成、怎么进物理层。
6. **`physics/radiation.py`** ——只看公式和 19.342 自检，实现细节可以跳。
7. **`losses.py`** ——为什么是 asinh。
8. **`train.py`** ——标准训练循环。
9. **`evaluate.py`** ——指标定义。
10. 想深挖再看 `experiment.py`（总装线）和 `config.py`（校验）。

---

## 13 现状与注意事项（读代码前必须知道）

1. **这份代码从未在本机跑过。** `REPORT.md` 第 0 节明确写了：交付时按指令没有执行 pytest / 训练，`runs/` 里没有 `metrics.csv`。
   所以：19.342 dBsm 是**解析值**；101k / 97k / 212k 是**按结构数出来的估算**；"M3 比 M0 好多少"目前**没有实测数字**，只有 `REPORT.md §7.2` 的预期区间。
2. **`loss.mode: complex` 会直接抛 `NotImplementedError`**（`losses.py:130`）。因为数据集只有幅度（4 列），复场损失需要 6 列（幅度+相位），目前只有 1 个样本有。
3. **M1 是简化 U-Net**（没有 46×180 的全分辨率解码器），它是"无物理对照"，不是某篇论文的严格复现。
4. **数据只有单频、单入射角（法向）、单极化、单一 20×20 规模。** 所有结论都限制在这个范围内。
5. `msgnn/__init__.py` 里设了 `KMP_DUPLICATE_LIB_OK=TRUE`，防止 Anaconda 下 torch 和 numpy(MKL) 的 OpenMP 冲突直接 abort。
6. `config` 对未知键**直接报错**——YAML 里拼错一个字段名不会被静默忽略，这是好事，但第一次改配置时要留意。

---

## 14 一页纸总结

```
任务：编码超表面（20×20，1-bit）→ 上半球 8280 个方向的 RCS 方向图
难点：镜面比弥散高 25–30 dB；逐码跑 CST 太慢；局部周期近似在镜面差 13.8 dB

模型：q = q0 + Δq(GNN) + b(全局复标量)
      q0  ← 单元库查表（物理，0 参数）
      Δq  ← 3 层消息传递（每节点 2 个数）
      b   ← 整图 mean-pool + MLP（每样本 2 个数）
      σ   ← 固定的衍射积分算子（0 参数，可微）
      loss← dB 域 asinh 压缩 MSE（sinθ 权重 + 主瓣加权）

GNN 一句话：agg_j = Σ_i MLP([h_i, h_j, e_ij]);  h_j ← LN(h_j + MLP([h_j, agg_j]))
           = "8 邻域上的可学习卷积"，和 3×3 卷积同构，但权重由边特征决定

对照：M0 无参数 / M1 CNN 212k / M2 GNN 直接出 q 97k / M3 残差 101k
```

---

*本文档由代码静态阅读生成；所有行号以 `D:/GNN/gnn/` 下的当前文件为准。*
