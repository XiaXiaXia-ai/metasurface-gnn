# P0 审计回应（2026-10-22）

对应 `docs/reviews/2026-10-22_p0_audit.md`（结论：有条件通过，修完 Z1/Z2/Z3 后可提交）。

## 一、阻断与重要项

| 编号 | 结论 | 处置 |
|---|---|---|
| **Z1** B=1 不去均值 | **接受，已修** | 删掉 `n_graphs <= 1` 早退，B=1 也走去均值。现在同一张图无论单独推理还是混在 batch 里，输出一致；`predict.py` 的 `|b|` 诊断因此恢复意义。 |
| **Z2** `max_samples` 在 `scan_cases` 内截断会污染快照 | **接受，已修** | 截断改为**调用方参数**：`scan_cases(..., max_samples=None)`，只有 `experiment.build_context` 传 `cfg.data.max_samples`；`build_snapshot` 不传 → 快照仍是全量。 |
| **Z3** 标量 `area_mm2` 抛 IndexError、精度措辞过度 | **接受，已修** | 标量自动广播成 `(N,)`；docstring 的 "bit for bit" 改为 "up to float32 rounding（numpy 参考为精确）"。 |
| **Z4** complex 未在 config 层拦 | **暂缓** | config 层无法知道数据列数，拦在这里会造成"配置正确却跑不了"。当前在 `build_loss` 报错，代价是 `build_context` 之后才失败（几秒）。列入 P1：给 `build_context` 加前置检查。 |
| **Z5** README / 架构 / REPORT 口径未同步 | **接受，已修** | REPORT §8(2) 改写为"mean(Δq) 恒为 0 是构造性质，验收看 \|b\| 与 std(Δq)"；README 标注 complex 未接通；架构文档新增 §7.5。 |
| **Z6** 零新增测试 | **暂缓** | 本机不执行代码，新测试无法验证真伪。列入 P1（待可运行环境）：B=1 vs B=3 一致性、area 标量/向量、max_samples 不污染快照、严格 4 列拒 6 列。 |

## 二、建议项

| 建议 | 结论 |
|---|---|
| sha256 用 raise 而不是"剔除记日志" | **驳回**：数据完整性优先，静默剔除样本比硬失败更危险；README 已写明"快照哈希不一致即终止"。 |
| 6 列文件是 skip+warn 而非报错 | **驳回**：6 列样本根本不在 `results/ff` 目录下，扫描不到；真出现就是事故，warn 足够且不误伤。 |
| area docstring 承诺 local frame 但接口没有 | **接受，已修**：措辞改为"curved array 预期同时传 A_n 与局部 frame（frame 接口在 P2）"。 |
| `m3 + global_branch:false` 会失去均匀分量 | **接受，记录**：这是有意的消融配置，README 里注明"该变体只用于消融，不能当 M3 交付模型"。 |
| list 分支未递归 | **接受，P1**。 |

## 三、回归

审计判定 19.342 自检、M0/M1/M2、零初始化下 M3 ≡ M0 均无风险；旧 M3 checkpoint 在 B≥2 下数值会变，
已在 REPORT 注明"改造前 checkpoint 与本次口径不可直接比较"。

## 四、提交结论

Z1/Z2/Z3 与 Z5 已按审计意见修完；Z4/Z6 与两条建议项转为 P1。
**本轮允许提交**。下一轮（P1）开始前仍不运行任何代码，等环境更换后再做端到端验证。
