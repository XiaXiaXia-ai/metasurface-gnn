# 几何修复复核的回应（2026-10-22，第二轮）

对应 `docs/reviews/2026-10-22_geometry_fix_audit.md`（F1/M1/M3/M4 通过，M5 未通过，另有 4 条旁路问题）。

## 处置

| 项 | 结论 | 处置 |
|---|---|---|
| **M5-a** `test_geometry.py:37` 恒真断言 | 接受 | 删除；改为与解析导数 `(cosθ,0,−sinθ)` 逐点比较 |
| **M5-b** `:57` 步进方向错（idx=1 是 v 邻居） | 接受 | 改为沿 u（索引 +N）取步进，并与中点处的 t1 比较；容差取 O((P/R)²) 量级 2e-3 |
| **M5-c** `:95` 依赖 `test_graph.py` 的 env fixture | 接受 | 不再跨模块借用；测试内自带 `_FakeCase`（只提供 build_graph 真正读的 4 个字段）+ `UnitLibrary.floquet` |
| **M5-d** 用例数 6 而非 7 | 接受 | 现为 6 个，回应文档不再写 7 |
| **I1** `evaluate.py:124` 基线仍用平面位置 | 接受，已修 | `predict_baseline` 现在与算子同一几何（`surface.positions()`） |
| **S3** `build_graph` 不校验 Surface | 接受，已修 | 入口调用 `surface.check()`，radius=0 会立刻报错而不是产生 NaN |
| 21 的边特征 2D/3D 混用 | 记录 | `pos_xy=pos[:,:2]` 算的是**投影**边特征，追加的 `r3d` 是三维距离；两者在柱面上不等，已在文档标注 |
| 文档漂移 4 处 | 接受，已修 | 面积已接入；"无新分支"改为"惰性分支"；曲率差边特征改为未实现；模块 docstring 更新 |

## 仍然成立的限制（不宣称已补齐）

- geometry 默认关闭；`geometry=true` 需要 `surface=cylinder` 且半径 > 0；
- 网络输入侧仍缺 `pos/frame`（经 `collate` 进入 batch）——只进节点特征，不进 batch 张量；
- 单一数据集只能有一种曲面（算子只建一次）；
- 该 6 个新列在单一 R + 正入射下退化，价值要等 R 变化与斜入射。