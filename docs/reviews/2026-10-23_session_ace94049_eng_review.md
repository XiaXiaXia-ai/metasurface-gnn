# 工程可行性与回归风险审计（只读）：ace94049 的 D1/D2/D4/D5、M2/M4/M6/M7/M8

- 对象：`docs/reviews/2026-10-23_session_ace94049_suggestions.md`（尚未采纳）+ 当前代码 `D:\GNN`。
- 方式：**只读静态审查**，未运行 python / pytest / 训练 / smoke / git，未改源码，唯一写入是本文件。`file:line` 为本次逐行阅读的行号；**[推演]** = 静态推导；实测数字引自 `cst/demo_out/numbers.json`、`cst/一份真实数据的全流程演示.md`、`cst/demo_out/train_console.txt`，**非本轮执行**。
- 现场：`D:/dataset` 现有 **486** 对 ff/res（日志记 472/1000，仍在长）；全仓 **0 个 `.pt`、0 个 `normalizer.json`**，唯一存量在仓库外 `D:/DSHNESS/GNN/demo_out/run_m3_demo/`。

## 0 结论

**方向对，但清单 §5 的 P0 不能按原样执行。** 10 条里 3 条（D1/D2/D3+M2）改"维度或 state_dict 键"、2 条（D4/M4）改"频率语义"，而本机禁跑（`gnn/README.md:6`、`docs/gnn_architecture.md:101`、`2026-10-22_p0_audit_response.md:14`）⇒ 其验收判据"重训 demo，看 spec_err 是否从 0.16 涨过 0.3"**一条都拿不到**。应重切 P0a/P0b（§6、§7）。

| # | 裁定 | 一行依据 |
|---|---|---|
| D1 删 `normal_z` | **采纳**（与 D2 同一提交） | 平面恒 1（`build_graph.py:95`）；曲面时 `cos_inc ≡ n_z`（`geometry.py:134` 对 `build_graph.py:144`，`geometry.py:146-148` 自承） |
| D2 删 `gamma_abs` | **采纳**（同上） | `abs(Gamma)=hypot(re,im)` 零新信息；gamma 整块与 bit 一一对应（`GNN代码解读.md:224` 自承） |
| D3+M2 冻结 b 常量 | **需实验裁定** | 只报了 b 的模的 std（0.374±0.011，demo 文档 :472），**逐例相位散布没入档**；改键后旧 ckpt 必崩，M3-noglob 消融消失 |
| D4 删 `freq_ghz` 形参 | **与现状冲突** | `unit_library.py:73` 是**位置传参**：删形参 → 10.0 绑到 `gamma_source` → ValueError，四条入口全挂；且与 M4 方向相反 |
| D5 删 `get()` 的 `pos` | **驳回** | 省不到内存：numpy `pos` 常驻 `self.graphs`（`build_graph.py:160`），`get()` 只是 4.8 KB 副本，`collate` 根本不收它 |
| M4 per-case λ | **与现状冲突** | λ 只进特征；q0/算子/M0 仍单频（`build_graph.py:269`、`experiment.py:160-166`、`evaluate.py:135`），486/486 例都 10.0 GHz ⇒ 今天做 = no-op + 三处不一致 |
| M6 B=1 修复 | **采纳**（改 `pipeline.py:99`，不改 predict） | B=1 确实没 reshape；但**只有 q 坏**，eth/eph/sig_db 都是 `(1,M)` |
| M7 测试同步 | **采纳**（断言要改写） | `mean(Δq)=0` ≠ `mean(q−q0)=0`（后者恒等于 b）；照字面写会得到一条永远失败的测试 |
| M8 三个配置开关 | **驳回** | `state_gate` 无消费者、`freeze_b` 与 M2 相矛盾、`freq_list` 与 M4 同一坑；先加 schema 即重演"死配置" |

## 1 逐条裁定的依据与最小执行

**D1 采纳。** `build_graph.py:41-42` 的 `normal_z` 只由 `:95` 的 `nz` 喂入，平面恒 1、标准化后恒 0（`normalizer.py:71-74` 把 std 置 1）。曲面路径更明确重复：`cos_inc = -(n̂·k̂)` 且默认 `k̂=(0,0,-1)`（`geometry.py:119,134`）⇒ `cos_inc` 就是 `frames[:,2,2]`。最小执行：删 `:41-42` 的字符串与 `:95/:100` 的 `nz`，同批改 §2 全表；并在 `:110` 前加 `assert x.shape[1] == len(NODE_FEATURES)`——现在元组与 `cols` **没有任何绑定**，只改一处就静默漂移。

**D2 采纳（与 D1 合并成一次 9→7）。** `gamma_re/im` 已与 bit 双射（`build_graph.py:97-99`），`:99` 的 `np.abs(g)` 再加一层确定性冗余。不要分两次做：9→8→7 会把 §2 的 14 处引用改两遍、normalizer 重拟两遍。

**D3+M2 需实验裁定。** 现状：`residual_gnn.py:52-53` 的 `glob` 由 `:83-86` mean-pool 出 2 个数，`pipeline.py:83-86` 按 `batch` 索引相加。反对"已退化成常数"的证据缺口：清单只引 b 的模的 std 与 `corr(|b|,|b_oracle|)=−0.197`（`diagnose_demo.py:89` 就是按**模长**算的），而 `diagnose_demo.py:63` 明明打印了 `arg b` 的 std 却没写进文档；若相位有 30° 级散布，"一个常数 b"会吃掉一个真实的每样本自由度。最小执行（**先做零成本判据，不先改模型**）：在 `D:/DSHNESS/GNN/demo_out/diagnose_test.npz` 上补算 `std(arg b)` 与复相关；判据 b 的模 std<0.03 **且** `arg b` std<15° 才做。改法：`nn.Parameter(torch.zeros(2))`、删 `residual_gnn.py:52-60` 的 glob 与零初始化分支、`pipeline.py` 用标量广播 `q = q0 + n + b[0]`，params 101060→96770（`numbers.json:47`）；旧 ckpt 只能 `strict=False` + 显式缺键白名单。

**D4 与现状冲突。** `floquet_gamma` 的 `freq_ghz` 确实未使用（`unit_library.py:44-50`），但"删形参"要连带 `UnitLibrary` 字段与 8 处调用（§4），收益只是"名字诚实"，而 M4/M8 正要让频率变成真参数——方向相反。最小等价执行（1 行）：`:44` 里加 `if float(freq_ghz) != 10.0: raise ValueError("only the 10 GHz calibration exists")`，docstring 注明"仅 10 GHz"。

**D5 驳回。** 全库唯一读 `get()["pos"]` 的地方**不存在**（`tests/test_graph.py:80` 读的是 `build_graph` 的返回，不是 `get()`），这点清单说对了；但"批处理里白占内存"不成立：`collate`（`build_graph.py:228-256`）不接收 `pos`，`self.graphs[i]["pos"]` 永远常驻。收益 ≈ 0，代价是删掉曲面路径唯一能随 batch 流动的三维几何（`2026-10-22_physics_audit.md:306` 的 P2 第 10 条正是要接 geometry provider）。

**M4 与现状冲突。** `self.lam`（`build_graph.py:183`）只喂 `node_features`/`edge_features`；q0 来自 10 GHz 库，远场 `k`/`c` 来自单一算子（`radiation.py:186-187`、`experiment.py:160-166`），M0 基线又走 `cfg.physics.freq_ghz`（`evaluate.py:135`）。per-case λ 会让"特征按 f 归一、物理按 10 GHz"，且 normalizer 把不同 f 的 x/λ 混统计。现存 486 例全 10.0 GHz（抽检 0000/0200/0300/0400/0480 的 res json）。最小前置（可先做）：在 `build_context` 断言三个 split 的 `Case.freq_ghz` 全等于 `cfg.physics.freq_ghz`，把"静默丢频率"变显式；真实现留给 M5。

**M6 采纳。** 病根确认：`pipeline.py:99` 条件是 `n_graphs > 1`，B=1 时 `q_re` 保持 `(N,)`，`predict.py:52` 的 `[0]` 取到标量，`:80-83` 的 `|dq|`/`mean(dq)` 因此是"1 个节点 vs 400 个 q0"，无意义（与 demo 文档 :496-503 判断一致）。但 49-51 行是对的：`radiation.py:247-249` 会 unsqueeze，`:267-268` 的 `v[0]` 是**block 维**不是 batch 维，故 fields 恒 `(B,M)`。最小执行：`pipeline.py:99` → `if ptr is not None:`（B=1 时 `sizes=[N]`，`view(1,N)` 成立），一处覆盖 predict/inference/smoke 尾批；配套改 `diagnose_demo.py:5-8` 的 docstring 与 `:24-25` 的旧树路径。

**M7 采纳。** 参数化：`tests/test_graph.py:69` → `(400, len(NODE_FEATURES))`；`:86-88` 的 `x[:,7]/x[:,8]` → `NODE_FEATURES.index("boundary")`；`:131,:150` 的 `build_pipeline(cfg2, 9, 5, …)` → `len(NODE_FEATURES), len(EDGE_FEATURES)`；`tests/test_geometry.py:101,106` 同用 `len(NODE_FEATURES)`。新增不变量测试**必须**写成 `dq = q − q0 − b` 再断言 `mean(dq)≈0`（`b` 从 `net(batch)["glob_re"][batch]` 取），否则它测的是 b 本身；更省事的替代是断言同一张图在 B=1 与 B=3 下 `sig_db` 逐点一致（这才是 p0_audit Z1 的回归保护）。float64、tol 1e-9；float32 只能 1e-6 级。

**M8 驳回。** `graph.state_gate` 的消费者是 A3（未采纳、且等 CST 判据）；`model.freeze_b` 冻结在 0 就退化成 M0、冻结在 0.37 则把标定值写死；`physics.freq_list` 与 M4 同坑。`config.py:236-240` 的"未知键硬报错"是特性，不需要预声明；先加 schema 会重现 `2026-10-22_physics_audit.md:275` 的"死配置"。

## 2 副作用 I：9→7 的硬编码清单（D1+D2 必须同批）

| 位置 | 内容 | 不改的后果 |
|---|---|---|
| `build_graph.py:4-16,41-42,97-100` | docstring 列号 0..8、元组、`cols` | 三处须同时改；当前无断言绑定（建议补） |
| `tests/test_graph.py:69,86-88` | `(400,9)`、`x[:,7]`、`x[:,8]` | 断言失败 / 索引错 |
| `tests/test_graph.py:131,150` | `build_pipeline(cfg2, 9, 5, …)` | `Linear(9,64)` 收 7 维 → RuntimeError |
| `tests/test_geometry.py:101,106,107` | `9`、`9+len(GEOM_NODE)`、`5+len(GEOM_EDGE)` | 失败；`:15` 还需 import `NODE_FEATURES` |
| `docs/gnn_architecture.md:28` | "节点特征 9 维" + 列名 | 文档错 |
| `docs/geometry_representation.md:43` | "9 列变 15 列" | 应为 7→13 |
| `gnn/REPORT.md:134` | 特征 9 维 | 文档错 |
| `cst/GNN代码解读.md:108,119,212,215-216,226,291,444,454` | 三处副本（表 + node_enc + 输入形状） | 文档错 |
| `cst/walkthrough_demo.py:170,171-177,357,360` | "9 维"、`row[8]`、`(9,5)` | **脚本直接 IndexError**（`:211` 的 enumerate 安全） |

- 不必动：历史产物 `cst/一份真实数据的全流程演示.md:141,360`、`cst/demo_out/*.txt`、`docs/logs/2026-10-22.md:74`；加一句"2026-10-23 起 7 维"即可。冻结副本 `gnn/runs/verify/shadow/**` 与 `patch_shadow.py` 的 `assert count` **不要改**，但要注明它与主包已分叉。
- 实际失效面比清单说的小：仓库内 0 个 `.pt`/normalizer，唯一存量是仓库外 9 维 demo run。失效表现是 `normalizer.py:48` 的广播 ValueError（`normalizer.py:19-25` 只存 mean/std，无维度元数据）与 `load_state_dict` 的 size mismatch（`predict.py:43`、`evaluate.py:159`）。建议顺手加 `n_x/n_e` 校验。

## 3 副作用 II：D3 的 state_dict / 配置 / 消融

- 键变化：`net.glob.net.0.{weight,bias}`、`net.glob.net.2.{weight,bias}` 消失（4290 = 64×64+64 + 64×2+2，与 `numbers.json:47` 的 101060 对得上），新增 `net.b`。
- 读点全部 strict：`evaluate.py:159`、`predict.py:43`，另有 `cst/fig_m3_demo.py:27`、`cst/diagnose_demo.py:31-32` ⇒ 旧 ckpt 一律 Unexpected/Missing key。
- 配置变死键：`pipeline.py:142` 仍传 `global_branch`，`config.py:72` 与 `configs/train_m3.yaml:22` 保留；`gnn/README.md:92`、`gnn/REPORT.md:128,276`、`GNN代码解读.md:448,477,707` 需改。
- 实现坑：`q` 是 `(B*N,)`。若 b 是数据集级常数，`q_re + b[0]` 的标量广播是对的；若要每图不同，必须 `b.expand(B,2)[batch]`，否则 B>1 时静默给所有图加同一个数。零初始化还必须显式把 b 置 0（`residual_gnn.py:54-60` 现在只清 head/glob），否则"M3 初始 = M0"（`REPORT.md:126`）失守。

## 4 副作用 III：D4 的 `freq_ghz` 调用点（8 处 + 2 处上游）

`unit_library.py:55`（无参默认）、`:63`（default_factory）、**`:73`（唯一位置传参处）**、`:77,90`（from_csv）、`data/build_graph.py:269`、`experiment.py:140`、`tests/test_graph.py:30`、`tests/test_geometry.py:98`；上游 `config.py:57,273-274`。**`physics/baseline.py` 不在此列**：它只收 `UnitLibrary` 对象（`:29-31,134`），换库会自动跟随 `ctx.library`。删形参的正确顺序：先改 `:73` 与四个 `UnitLibrary.floquet` 调用点，再删 dataclass 字段 `:64` 与 `from_csv` 形参，最后同步 config——否则 config 的 `freq_ghz` 才真成死键。

## 5 副作用 IV：predict 的 B=1 是否还有独立问题（已逐行核）

- `pipeline.py:96-104`：reshape 只在 `n_graphs > 1`；B=1 跳过。**这是唯一病根。**
- `radiation.py:245-249` 算子自己 unsqueeze；`:267-268` 的 `v[0]` 取 block 而非 batch ⇒ fields 恒 `(B,M)`。故 `predict.py:49-51` 的 `[0]` 正确，只有 `:52` 的 q 错。
- 最小修法放 `pipeline.py:99` 一行即可，predict 不必加 `_vec`。附带：`predict.py:71` 的 npz 现在存的 q 是标量，修完后才是 `(N,)`；`diagnose_demo.py:43` 用 `q_of` 自行 ravel，未受影响。

## 6 P0（≈2 h）在本机能否验证：不能

1. **禁跑**：pytest / smoke / 训练均不许，任何"spec_err 有没有变差"的判据都拿不到。
2. **无基线**：0.16 dB 来自 247 例快照的 44 例 test（demo 文档 :27），磁盘上已 486 例；重训会重新切分，对照基线自己就变了。要做 A/B，必须在**同一份 snapshot** 上跑"旧代码 vs 新代码"两次；而旧代码只有 shadow 副本，且它早于 B3/B2 修复，不能当基线。
3. **旧树耦合**：`cst/train_demo.py:17`、`diagnose_demo.py:24-25`、`fig_m3_demo.py:20-21`、`walkthrough_demo.py:44` 全指 `D:/DSHNESS/GNN/demo_out`；在 `D:\GNN` 下跑会写/读另一棵树，产物不进仓库，违反 `docs/CONVENTIONS.md:9,35`。
4. **M0 不能当替身判据**：M0 只依赖 q0 与算子，不受特征维影响；会变的是训练后的 M3——那必须真跑。
5. 结论：P0 只能静态闭合 **M6 + M7 + D4(断言) + 脚本路径**；**D1/D2 与 D3/M2 推迟**到第一个能跑 pytest+5 epoch 的环境（`train_console.txt:20`：5 epoch = 37.5 s，成本不是障碍，环境才是）。

## 7 建议的落地顺序（修正版）

- **P0a（今天，零数值风险）**：M6 一行、M7 断言改写、D4 断言、`diagnose/fig/train_demo` 改仓内路径或加 `--run` 参数；9→7 的文档先不动。
- **P0b（首次可运行，一次提交）**：D1+D2 + §2 全表 + `len(NODE_FEATURES)` 断言；pytest 全绿后再跑 5 epoch，把 spec_err/rho_lin 记为**新基线**（与"9 维同环境重训"比，不与 0.16 比）。
- **P1（同环境，一次实验）**：D3+M2 的 `arg b` 判据；通过才改参数化，并把 README/REPORT 的 b 语义一起改。
- **P4**：M4 与 M5、per-sample k/c、per-case 库同一提交。**D5 不做；M8 不做。**

## 8 未能确认

未运行任何测试/训练，"会失败/会通过"均为推演；例外：§5 的 `(B,M)` 形状结论是逐行读码确认的。旧 ckpt 在新代码下的数值漂移未加载、未推理。两棵树是否仍按 `CONVENTIONS.md:24` 双树共存：只读可见 `D:\DSHNESS\GNN` 仍在；若已决定并入 `D:\GNN`，则 §6.3 从"暂缓"升级为"阻断"。
