# r42r5 曲面阵列：建模 + 仿真 + 批量（可迁移包）

三份文件，互相 import，放在**同一个目录**即可运行：

| 文件 | 作用 |
|---|---|
| `r42r5_curved.py` | 建模器：生成完整 CST VBA 宏（几何 + 求解器 + 导出）。纯 Python，不依赖 CST |
| `run_bas_case.py` | 单例执行器：把宏切段，驱动 CST 建几何 / 求解 / 自检 / 导出 6 列复场 |
| `curved_batch.py` | 批量：`--n` 定阵列规模、`--count` 定组数，带相位门、断点续跑、元数据指纹 |

---

## 1 环境要求

- **CST Studio Suite**（2026 已验证；需要 **TLM 求解器** license）
- **Python 3.9+**，只需 `numpy`
- CST 的 Python 接口库：`<CST安装目录>\AMD64\python_cst_libraries`

脚本会**自动找**这个目录，顺序：

1. 环境变量 `CST_PYTHON_LIB`（非标准安装路径时用它）
2. 环境变量 `CST_INSTALL_DIR` + `\AMD64\python_cst_libraries`
3. 在 `Program Files` / `Program Files (x86)` / `D:\Program Files` 下扫 `CST Studio Suite*`
4. 如果本来就 import 得到（例如直接用 CST 自带的 python），什么都不用做

检查是否找对：

```bash
python -c "import run_bas_case as m; print(m.CST_LIB)"
```

---

## 2 快速开始

```bash
# 1) 只生成宏，不碰 CST（先看一眼要建什么）
python curved_batch.py --n 8 --count 3 --dry-run --out ./batch/n8

# 2) 先跑相位门（uniform0 / uniform1 各一例，5-10 min），不过就退出
python curved_batch.py --n 8 --count 20 --gate --R 200 --out ./batch/n8

# 3) 正式批量
python curved_batch.py --n 8 --count 200 --R 200 --out ./batch/n8

# 4) 中断后原样再跑一次即可续跑（已完成的自动跳过）
python curved_batch.py --n 8 --count 200 --R 200 --out ./batch/n8
```

**两个旋钮**：`--n` 每边单元数（8 / 12 / 20），`--count` 跑多少组。
`--cells 64` 是等价写法（总数，必须完全平方）。

---

## 3 模型与仿真设置（这是"物理"本身，改之前先想清楚）

| 项 | 值 | 说明 |
|---|---|---|
| 阵列 | `n × n`，`block=2` | n=8 → 4×4 宏码；n=12 → 6×6 |
| 周期 P | 14.0 mm | |
| 曲面 | 圆柱，`R` 可调（默认 200） | `x=R sin(u/R)`、`z=R(1−cos(u/R))`，凹向 +z |
| 基板 | 1.5 mm，εr 2.65，tanδ 0.0013 | 半径方向 R … R+1.5 |
| 地板 | **0 mm 零厚度 PEC** | 在 R+1.5 处 |
| 贴片 | 圆形 PEC，**bit0 r=5.0 / bit1 r=4.2 mm** | 壳半径 199.82–200.02，无 lift |
| 激励 | 平面波 k=(0,0,−1)，E=(1,0,0) | 9–11 GHz |
| 监视器 | `farfield (f=10) [pw]` | 10 GHz |
| **求解器** | **TLM** | **不要用 FIT**：默认网格会把 177.6° 的相位差做成 122°，标签直接废掉 |
| 边界 | 六面 open，背景 15 mm | |
| 导出 | 8280 方向（θ 0–90、φ 0–358，步 2°） | 6 列：`theta phi |Eθ|dBsm ∠Eθ |Eφ|dBsm ∠Eφ` |

---

## 4 必看的检查点

跑完第一例后对照这几条，任何一条不对就停下来：

| 检查 | 应有值 | 不对说明什么 |
|---|---|---|
| 相位门 Δφ（uniform1 − uniform0 @θ=0） | **−177.6° ± 5°** | ≈ −122° → 跑成 FIT 了；正负反了 → 半径写反 |
| 贴片体积（`selfcheck_*.txt`） | r=5.0 → **15.708 mm³**；r=4.2 → **11.084 mm³** | 数量或半径不对 |
| 网格 cells（n=8） | 0.50–0.53 M | 明显更少 → 贴片没建出来 |
| 网格 cells（n=12） | 1.08–1.13 M | 同上 |
| 求解耗时（n=8 / n=12） | ≈ 190 s / ≈ 1260 s（28 线程） | 线程数少会成倍变慢 |
| 导出 | 8280 行 × 6 列、全有限 | 导出块被截断 |

**参考量级**（本机 28 线程实测）：n=8 天底 −12.2 ± 5.4 dBsm、n=12 −9.1 ± 4.8 dBsm。

---

## 5 输出结构

```
<out>/meta.json                 unit_id / 全部参数 / 16 位指纹
<out>/gate.json                 相位门结果
<out>/codes/code_XXXX.txt       宏码（n=8 → 16 位；n=12 → 36 位）
<out>/results/res_XXXX.json     天底 / 峰值 / 远区均值 / cells / 计时
<out>/results/ff/ff_XXXX.txt    8280×6 复场
<out>/work/case_XXXX.bas        实际执行的宏
<out>/work/run_cXXXX.json       逐段计时 + 网格 + TLM 行数 + selfcheck
<out>/logs/progress.jsonl
```

三个防呆机制：

1. **指纹**：换 R / 换单元 / 换 block 后往同一目录跑会直接报错，不会静默混数据；
2. **续跑**：`res` + `ff` 都在就跳过；
3. **补写 + 一致性自检**：CST 跑完但写 json 失败时从已有 ff 重建；结束时断言"每个 ff 必须有对应 res"。

---

## 6 换机器/换参数时的注意

- **不同 R 用不同 `--out`**（指纹会拦，但别走到那一步）。
- **一次只开一个批量任务**：CST 会把 CPU 吃满，并行没有收益。
- 每例在 `work/` 下留 ~50 MB（n=8）/ ~100 MB（n=12）的工程目录，200 例约 10 / 20 GB。
  不需要重导出的话可以手动清 `work/c*` 目录。
- 批量跑时不要同时在该 CST 里手工开工程（会抢 GUI 焦点）。
- 首次运行如果报 `import cst` 失败，先跑第 1 节的自检命令确认 `CST_LIB` 路径。

---

## 7 已知瑕疵（数据用之前要知道）

1. **网格不固定**：CST 自动网格随贴片半径变化，cells 在 ±5% 内浮动。严格 A/B 会掺入网格差。
2. **uniform 两态电平不对称**（n=8 时差 1.2 dB），原因未定。**不要用 uniform 做幅度归一**，只当相位门。
3. **未做网格/时长收敛性检查**：TLM 的停止判据用默认设置。
4. `block=2` 意味着一个宏位覆盖 2×2 个单元，宏码长度是 `(n/2)²`。

---

## 8 验证记录

| 项 | 结果 |
|---|---|
| n=8, R=200, 200 例 | 相位门 −178.40°，零失败，11.0 h |
| n=12, R=200, 200 例 | 相位门 −177.97°，零失败，72.2 h |
| 贴片体积 | 与解析值差 +0.008% |
| 求解器 | 每例 `Model.log` 里 "(TLM Solver)" 61 行、FIT 0 行 |
| 导出 | 400/400 为 8280×6、全有限 |
---

## 9 换阵列规模（N=16 / N=20）

**物理设置完全不变**：同一 R、同一单元、同一 TLM、同一导出。只有两件事跟着变：

| N | 宏码长度（block=2） | 贴片数 | 宏文件大小 |
|---|---|---|---|
| 8 | 16 位（4×4） | 64 | 116 KB |
| 12 | 36 位（6×6） | 144 | 232 KB |
| **16** | **64 位（8×8）** | **256** | **395 KB** |
| **20** | **100 位（10×10）** | **400** | **605 KB** |

用法完全一样：

```bash
python curved_batch.py --n 16 --count 20 --gate --R 200 --out ./batch/n16
python curved_batch.py --n 20 --count 20 --gate --R 200 --out ./batch/n20
```

### 成本会涨得很凶（务必先测一例）

实测两点：n=8 是 154 s/例（0.50 M cells），n=12 是 1263 s/例（1.10 M cells）。
**尺寸涨 1.5 倍、时间涨 8.2 倍**——因为结构变大后脉冲要走更久，时间步数随之增加。

两种外推（差异很大，只作量级参考）：

| N | cells 估 | 按 L³ 物理标度 | 按两点幂律拟合 |
|---|---|---|---|
| 16 | ~2.0 M | **≈ 50 min/例** | ≈ 1.6 h/例 |
| 20 | ~3.1 M | **≈ 1.6 h/例** | ≈ 5 h/例 |

对应 200 例：n=16 约 **4–13 天**，n=20 约 **13–41 天**。

**所以不要一上来就 `--count 200`。** 推荐流程：

```bash
# 第 1 步：跑 1 例，量出真实单例耗时（同时验证 605 KB 宏能被 CST 正确执行）
python curved_batch.py --n 20 --count 1 --gate --R 200 --out ./batch/n20

# 第 2 步：看 logs/progress.jsonl 里的 solve_s，再决定 count
#         续跑是免费的，已完成的会跳过
python curved_batch.py --n 20 --count 60 --R 200 --out ./batch/n20
```

### 一个必须实测的风险

n=20 的宏约 **605 KB**（400 个贴片、每片 2 次布尔）。执行器把几何块作为**一个** history 条目送进 CST，
n=12 的 232 KB 没问题，605 KB 没有验证过。第一次跑 n=20 时请确认：

- `work/run_c0000.json` 里 `status` 是 `ok`、`build_s` 合理（不是几百秒）；
- `selfcheck` 里有 **400** 行 `patch_XX_YY`；
- `tree_items` 约 400+。

如果 history 块太大导致失败，拆成两次 `add_to_history`（前 200 片 / 后 200 片）即可，几何结果相同。