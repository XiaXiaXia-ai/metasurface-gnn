# 曲面几何的表征（2026-10-22）

> 起因：评审发现 `normal_z` 这一个标量不足以表征曲面或复杂曲面。本文给出充分表征的清单、
> 已落地的接口，以及仍缺的部分。

## 1 为什么一个 `normal_z` 不够

`normal_z = n̂·ẑ` 只回答“这个单元相对全局 z 轴倾斜多少”，它丢失了：

| 丢失的信息 | 后果 |
|---|---|
| 局部坐标系 (t1, t2, n) | 无法把入射波分解到单元自身的基底，斜入射的 TE/TM 与极化投影都无从定义 |
| 局部入射角 cos_inc | 单元库只能查法向响应，曲面边缘必然错；背照/遮挡也无法判断 |
| 主曲率 κ1, κ2 | 同样的 n̂ 可以是平面、柱面、球面，曲率决定相邻单元的相位变化率与互耦强度 |
| 单元面积 A_n | 远场是 ∫Γ dA，面积变化（投影/拉伸）直接改变权重 |
| 单元在内禀坐标里的位置 | 曲面上的“邻接”与平面不同，边特征需要 3D 距离与法向夹角 |

也就是说，`normal_z` 是 `(t1,t2,n)` 的一个投影，信息量严格少于后者。

## 2 充分的最小集（每节点）

    r_n       (3,)      三维位置（mm）
    [t1,t2,n] (3,3)     右手局部系，t1 × t2 = n，n 指向反射侧
    A_n       scalar    物理单元面积（mm²）
    κ1, κ2    scalar    主曲率（1/mm），等价于 (H, K)
    cos_inc   scalar    = −k̂·n（>0 表示朝向入射波）
    k_t1,k_t2 scalar    k̂ 在局部系里的分量（单元库查表用）

边（i→j）再加：3D 距离 r_ij/λ、法向夹角 (1 − n_i·n_j)。
（曲率差 |κ1_i − κ1_j| 是下一步才需要的，目前未实现——法向夹角已经能区分柱面的弯曲方向。）

## 3 代码里现在有什么

`msgnn/data/geometry.py`（新增）：

- `Surface(kind, radius_mm)`：`plane` 与 `cylinder`（轴沿 y，弧长参数化）；
- `positions()/frames()/normals()/areas()/curvature()/incidence()`；
- 约定：`x = R sin(u/R), z = −R(1−cos(u/R)), y = v`，`n = (sinθ, 0, cosθ)`，R→∞ 回到平面；
- `from_config(cfg.graph)`：`geometry=False` 时返回 `None`，平面路径逐位不变。

`build_graph.py`（扩展，默认关闭）：

- 启用后节点特征从 9 列变 15 列：追加 `cos_inc, k_t1, k_t2, κ1λ, κ2λ, A/P²`；
- 边特征从 5 列变 7 列：追加 `r3d/λ` 与 `1 − n_i·n_j`（曲率的边级代理）。
  原有 5 列里的 `dx/dy/r/azimuth` 是 **xy 投影**值，柱面上 `r/λ ≠ r3d/λ`，两者刻意分开保留；
  该 7 列只在 `graph.edge_features=true` 时出现。
- 图字典新增 `frame/area/curv`，供辐射层后续使用；
- `graph.geometry=false` 时不启用新增特征列（新分支均为惰性求值，输出与改动前一致）。

配置：

    graph:
      geometry: true
      surface: cylinder
      surface_radius_mm: 200.0

## 4 仍缺（下一步）

1. **辐射层的局部极化基**：现在源的极化投影仍用全局 (cosθcosφ, −sinφ)，曲面应改为按 `frame` 逐节点投影；
2. ~~面积进入远场求和~~：已接入——`experiment.build_context` 在启用曲面时把 `surface.areas()` 传给 `FarFieldOperator(area_mm2=...)`，并与 `surface.positions()` 一起构建算子；
3. **遮挡 / 背照掩码**：`cos_inc ≤ 0` 只标记，尚未参与加权或屏蔽；
4. **单元库的角度插值**：`UnitLibrary` 的 (θ,φ) 表接口是死代码，需接上 `incidence()` 的输出；
5. **非柱面曲面**：球面/自由曲面需要 (u,v) 参数化 + 数值法向导数，`geometry.py` 已按此结构预留。

## 5 自检建议（换机后跑）

- `Surface('plane')` 的 `frames()` 应给出单位阵、`curvature()` 全 0、`positions()` 的 z=0；
- `Surface('cylinder', R)` 在 u=0 处 `n=(0,0,1)`、`cos_inc=1`；
- 同一 `R` 下相邻节点的法向夹角应等于 `P/R`（小角近似）；
- `graph.geometry=true` 时 `x.shape[1] == 15`、`edge_attr.shape[1] == 7`；
- `graph.geometry=false` 时输出与改动前逐位相同。