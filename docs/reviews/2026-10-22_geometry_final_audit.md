# 几何修复最终核验（2026-10-22）

> 只读静态审查：未运行 Python/pytest、未改源码。HEAD `a971f5b`；工作区 4 个已跟踪修改（config / build_graph / evaluate / experiment）+ 新增 `geometry.py`、`test_geometry.py`、三份文档。
> **结论：有条件通过**。上一份 `2026-10-22_geometry_fix_audit.md` 的三个阻断项（恒真/必败断言、缺 fixture、文档 3 处）全部修好，I1/S3 亦已修；无代码级阻断，条件均为文档/流程与一次实测。

| 核验点 | 证据（file:line） | 判定 |
|---|---|---|
| 1 测试 | 无自比断言（`:52/:53` 比解析量、`:62` 比 positions 导数）；`:60` 沿 u 用 **+N**（32→40），`:61` 参照中点 t1，`:62` atol=2e-3（正解残差 4.1e-4，行填回归 1.4e-1 → 必败）；无跨模块 fixture（自带 `_FakeCase` `:23-30`）；共 **6** 个用例（`:33/45/65/80/90/97`） | ✅ |
| 2 基线 | `evaluate.py:33` 已 import `geometry`；`:127-130` 用 `from_config` + `surface.positions()` 建 M0/M0g（plane 回退 `lattice_positions`，与旧路径等价） | ✅ |
| 3 check | `build_graph.py:127-128` 入口调用 `surface.check()` | ✅ |
| 4 文档 | `geometry_representation.md:58` 面积已接入、`:46` 改“惰性分支”、`:30` 曲率差标注未实现；`geometry.py:2` 已改 “plane and cylinder”（无 cylindrical next） | ✅（`:44` 未注 7 列需 edge_features=true） |
| 5 兼容 | `geometry=false` 仍 9/5 列、表达式与求值顺序未变（`build_graph.py:94-97,148-149`）；“无新分支”字面不成立（`:98,127,130,183` 为惰性守卫，文档已改口径）；`config.py:289-294` 拒绝 geometry+plane | ✅（附注） |
| 6 越界 | 改动仅清单内 4 文件 + 新 geometry/测试/文档；`geometry.py` 只依赖 numpy，无新依赖、无默认值改动（新增字段默认 False/plane/0.0） | ✅ |

**残余（建议级，不阻断）**：① 回应文档称“2D 投影边特征已在文档标注”不实——`build_graph.py:19` / `geometry_representation.md:44` 仍无 “projected”；② `predict_baseline` 的曲面取自 ref 配置，`--runs m0 runs/<曲面>` 顺序下 M0/M0g 仍是平面；③ `docs/logs/2026-10-22.md` 无本轮条目（CONVENTIONS §5）。

**提交建议**：**允许 commit**（代码/测试已满足上轮阻断项）；**push 前**补 ①③，并在目标机跑一次 `pytest gnn/tests/test_geometry.py`（本轮受命未运行，静态判定 6/6 应过）。`geometry=true` 仍不得宣称“曲面表征已补齐”。
