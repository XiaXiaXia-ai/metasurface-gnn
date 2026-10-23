# 另一会话（ace94049）提出的改动清单（原文）

> 来源：session-ace94049-2b35-4370-b3ea-30568581750c（"基于神经网络有限周期结构论文阅读"），
> 基于 demo 实跑数据分析后给出的 D/M/A 三类建议。原文照录，供审计讨论，**尚未采纳**。
===== [assistant] seq=622 turn=8 step=1 =====
[tool-call run_code]

===== [assistant] seq=632 turn=8 step=2 =====
# 改动清单：删除 / 修改 / 添加

按"**要不要动 CST**"分两批：前两批零仿真成本，今天就能做；后两批等 4 次超胞实验。

---

## 一、删除（5 项）

| # | 位置 | 删什么 | 依据 |
|---|---|---|---|
| D1 | `build_graph.py:41` `NODE_FEATURES` 第 8 列 | **`normal_z`** | 平面阵恒为 1，`_safe_std` 把 std 置 1 → 标准化后**恒等于 0**，纯死维度。曲面场景已有 `cos_inc` 承担同一信息 |
| D2 | `build_graph.py:99` | **`gamma_abs`** | 与 `gamma_re/im` 完全共线（$\lvert\Gamma\rvert=\sqrt{\text{re}^2+\text{im}^2}$），零新信息 |
| D3 | `residual_gnn.py:52` `self.glob` + `:84` | **全局支路的 MLP + mean-pool**（4290 参数） | 实测 $\lvert b\rvert=0.374\pm0.011$，跨 44 个样本只抖 3%，且 `corr(b_learned, b_oracle)=−0.197` → 它已经退化成常数。改为 `nn.Parameter(2)`，省 4288 参数且去掉一条不可辨识路径 |
| D4 | `unit_library.py:44` 形参 `freq_ghz` | **删掉这个假参数**（或补上真实现） | 函数体里**从未使用** `freq_ghz`，等于给人"支持多频"的错觉。要么实现 $\Gamma(f)$，要么显式删掉并注释"仅 10 GHz" |
| D5 | `build_graph.py:216` `out["pos"]` | 从 `get()` 的默认输出里**移除**（保留 dict 内部） | 前向路径完全不读它（`pipeline.py` 无引用），批处理里白占内存 |

> **不建议删的**：`bit_signed`（与 `bit` 共线，但 1 维换更快的收敛，值）、`boundary`（换成连续距离，见 M3）、`bits`（M1 要用）、`q0` 三份冗余（PyTorch 复数坑，实际只用 re/im）。

**连带**：`tests/test_graph.py:69` 的 `(400, 9)` 和 `GNN代码解读.md` 里的特征表必须同步。

---

## 二、修改（8 项）

| # | 位置 | 怎么改 | 依据 / 收益 |
|---|---|---|---|
| **M1** | `unit_library.py:38-39` | 把 `GAMMA_ABS/GAMMA_PH_DEG` 从**孤立单元**换成**阵中有效值**：$\Gamma_{0}=0.867\angle{-5.3°}+\overline{\Delta q}_{0}$、$\Gamma_1$ 同理（实测 $\overline{\Delta q}_0=+0.032+0.153j$、$\overline{\Delta q}_1=-0.031-0.146j$） | 实测 $\Delta q$ 均值项占修正量的 **23%**，且随状态反号——这正对应 224° 阵内相位差。**0 训练参数**吃掉这部分 |
| **M2** | `pipeline.py:78-86` | 配合 D3：`q = q0 + Δq + b_const`，`b_const` 为 2 个 `nn.Parameter` | 同上 |
| **M3** | `build_graph.py:94` | `boundary`(0/1) → **到边界的最小 λ 距离**：`min(i, j, n-1-i, n-1-j) * P/λ` | 单尺寸下与 `x_lam` 共线（几乎无收益），但它是**尺寸外推唯一的尺度不变量**，P5 做 10/40×40 时必需 |
| **M4** | `build_graph.py:183` | `self.lam = R.lam_mm(cfg.physics.freq_ghz)` → **per-case** `R.lam_mm(case.freq_ghz)` | `Case.freq_ghz` 已存在（`dataset.py:126`）却全程被丢弃，是跨频的**第一道墙** |
| **M5** | `radiation.py:186/200/237` | 缓存的 `cos/sin(k r·s)` 核 → 缓存**路径矩阵** `D[m,n]=r_n·ŝ_m`（mm，13 MB，频率无关），前向时按样本算 `k=2π/λ(f)` 再 `cos(kD)` | 一个矩阵取代 5 套核，任意频率免费。这是"λ 归一化"真正的落地点 |
| **M6** | `predict.py` / `diagnose_demo.py:7` | 修 `B=1` 时 `q_re` 未 reshape 成 `(1,N)` 的 bug（现在打印的 `|dq|` 不可信） | 你脚本注释里自己写了，但没修 |
| **M7** | `tests/test_graph.py:69,71` | 断言跟着特征数走；并**新增**一条：`mean(Δq)==0`（`_remove_graph_mean` 的不变量） | 防止 B3 的语义被后续改动破坏 |
| **M8** | `config.py` GraphCfg/ModelCfg | 加三个开关：`graph.state_gate: bool`、`model.freeze_b: bool`、`physics.freq_list: [..]` | 未知键直接报错的机制要求先加 schema |

---

## 三、添加（6 项）

| # | 加什么 | 在哪 | 前置条件 |
|---|---|---|---|
| **A1** | **2×1 超胞 + 4 种态组合的 Floquet 扫描**（00/01/10/11），输出复 Γ | 仿 `characterize_cell.py` 新脚本 | **无**，4 次求解 ≈ 20 min |
| **A2** | `UnitLibrary.from_calibration()`：读 A1 的结果表，给出阵中有效 $\Gamma_0,\Gamma_1$ 和耦合差 $\Delta\Gamma_{s_is_j}$ | `physics/unit_library.py` | A1 |
| **A3** | **态对门控**（4 参数）：`self.c=nn.Parameter(ones(2,2))`，`m *= c[bits[src],bits[dst]]` | `message_passing.py:41` | **A1 判据**：$\lvert\Gamma_{00}-\Gamma_{01}\rvert>0.05$ 才做 |
| **A4** | **邻居态均值**（1 列节点特征）：8 邻域 `mean(bit)` | `build_graph.py:node_features` | 无，随时可加（但先看 A3 结论，避免重复） |
| **A5** | **单元方向图 $f_e(\theta)$** 进算子 | `radiation.py` 投影段 | **先做判别**：在 train 上拟合 46 维 θ 乘性修正，看 60–90° 的 rmse（现 4.10 dB）掉不掉一半 |
| **A6** | `dataset_gen_v2.py`：5 频点 + 相位 6 列 | 已在 `后续工作计划.md` P0 计划中 | 无（但改了就要重跑 85 h，**必须等 M1/A1 定了再跑**） |

---

## 四、明确不做（3 项）

| 不做 | 理由 |
|---|---|
| **N×N 可学邻接矩阵（DGCNN 原版）** | 16 万参数 / 240 样本；你的算子已是 8280×400 的精确全连接核，物理上重复；实测 $\Delta q$ 与邻居态相关仅 −0.06/−0.28 |
| **三类网络分治（IC/EC/CC-NN）** | 那是张哲为"每单元只有 1 个自由度"设计的；你有 400 个并行节点 + 边特征，分治只会把 240 个样本切成三份 |
| **切比雪夫谱卷积** | 你的传播算子已显式给出，图只负责局部修正，空间消息传递更省更透明 |

---

## 五、执行顺序

```
P0 今天 · 0 CST · 约 2 h
   D1 D2 D4 D5  →  x: 9 → 7 维
   D3 M2         →  冻结 b（省 4288 参数）
   M6 M7         →  修 bug + 补测试
   ▸ 验证：重训 demo，看 spec_err 与 rho_lin 有没有变差
     （b 冻结后 spec_err 若从 0.16 涨到 >0.3 dB，说明 b 不是纯常数，回滚 D3）

P1 今天 · 0 CST · 20 min
   A5 的判别实验（θ 乘性修正）
   ▸ 若 60–90° rmse 掉一半 → 把 A5 提到 P2，其余降级

P2 明天 · 4 次 CST · 1 h
   A1 2×1 超胞  →  得到 Γ00/Γ01/Γ10/Γ11
   ▸ 判据：|Γ00−Γ01| < 0.02 → 停；> 0.05 → 进 P3

P3 按 P2 结论
   M1 + A2   →  阵中有效单元库（必做）
   A3 或 A4  →  二选一，不要都加

P4 P5 之前（多尺寸/多频数据就位后）
   M3 边界距离 + A6 数据集 v2 + M4 M5 频率管线
```

---

## 六、一个必须提前知道的副作用

**改 `NODE_FEATURES` 会让所有旧 `normalizer.json` 和 `best.pt` 失效**——特征维度变了，`config` 校验会直接报错。这不算问题（demo 重训几分钟），但要注意：

1. `make_splits.py` 不用重跑（划分与特征无关）；
2. `runs/*/normalizer.json` 必须重新 `fit`；
3. `GNN代码解读.md` 第 4.2 节的特征表和 `tests/` 的断言是**同一件事的三个副本**，改一处必须同步另两处，否则下次读代码的人会被误导。

---

**一句话总结这次改动的价值排序**：M1（改单元库，吃掉 23% 修正）> A5（单元方向图，可能是 60–90° 那 4 dB 的主因）> D1/D2/D3（清死维度、冻结 b）> M3/M4/M5（为 P5 铺路）> A3/A4（态依赖，等实验裁决）。**先别碰 GNN 结构**——数据显示你的瓶颈不在图，在单元库和单元方向图。