# 几何改动审计回应（2026-10-22）

对应 `docs/reviews/2026-10-22_geometry_audit.md`（结论：有条件通过，F1/M1/M3/M5 修复前不得启用 geometry=true）。

## 处置

| 编号 | 结论 | 处置 |
|---|---|---|
| **F1** frame 按行填、按列读 | **接受，已修** | `frames()` 改为按列填：col0=t1=(cosθ,0,−sinθ)、col1=(0,1,0)、col2=n=(sinθ,0,cosθ)。修完 `k_t1` 由 −sinθ 变 +sinθ，`normals()` 返回正确的 n。新增回归测试比较 `frames[:,:,0]` 与位置对 u 的解析导数，这正是原测试（只查 t1×t2=n 和 u=0）抓不到的。 |
| **M1** 鼓出方向写反 | **接受，已修** | 文档改为"中心最高、向 +z 凸、即照射侧"。 |
| **M2** 6 个新列在当前配置下退化 | **接受（记录）** | 确实：单一 R + 正入射时 cos_inc≡normal_z、k_t2≡0、A/P²≡1。它们的价值在 **R 变化**与**斜入射**出现之后；因此 geometry 只作为扩展位存在，不宣称"曲面表征已补齐"。 |
| **M3** plane + geometry 静默变宽 | **接受，已修** | `from_config` 对 plane 返回 None；`config._validate` 直接拒绝 `geometry=true & surface=plane`。 |
| **M4** 远场仍按平面算 | **接受，已修** | `experiment.build_context` 在启用曲面时用 `surface.positions()` 与 `surface.areas()` 建算子（`area_mm2`），远场与网络看到同一几何。限制：一个数据集内只能有一种曲面（算子只建一次），混曲面需按样本建算子，记为 P1。 |
| **M5** 无测试 | **接受，已补** | 新增 `tests/test_geometry.py`（7 个用例，含 F1 回归）。**未运行**（本机禁跑）。 |

## 建议项

- `collate` 不带 `pos/frame/area/curv` → P1（当前算子与样本几何一致，暂不影响）。
- 斜入射配置、相位中心、`z/λ` 进节点特征 → P1，与 `incidence()` 一起接。
- `UnitLibrary` 角度插值仍是死代码 → P1。

## 结论

本轮按审计要求修完 F1/M1/M3/M4/M5。`geometry` 仍**默认关闭**，且在修好前不会启用；
文档与代码都不宣称"曲面表征已补齐"，只称"预留了帧、面积、曲率与入射角的接口"。