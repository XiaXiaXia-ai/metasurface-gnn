# 记录与提交规范

> 规则来源：2026-10-21 用户要求 —— 现在及以后的相关文件、代码都要上传到 GitHub，实时记录与整理。

## 1 必须提交的内容

- 所有 **代码**（CST 自动化脚本、理论模型、训练/评估脚本）
- 所有 **文档**（计划、报告、诊断结论、数据契约）
- 所有 **图表**与**汇总表**（`figs/`、`*.csv`、`results.csv`）
- 每项实验的 **配置**（频率、几何、种子、划分）
- 工作日志 `docs/logs/YYYY-MM-DD.md`

## 2 不提交的内容

- CST 工程文件 `*.cst`（体积大、二进制）
- 单文件 > 20 MB 的原始数据；原始数据留在 `D:\dataset\` 等本机路径，仓库只记录**路径与生成脚本**
- 任何凭据（token、密码）
- `__pycache__`、`*.tmp`、`.tmpdir`

## 3 两条工作线

| 位置 | 角色 |
|---|---|
| `D:\DSHNESS\GNN\` | **在用的工作区**：CST 脚本、报告、图。数据集任务从这里运行 |
| `D:\GNN\`（本仓库） | **归档与版本**：`cst/` 是工作区的快照，`theory/`、`design/`、`analysis/` 是正式代码与文档 |

提交前运行 `scripts/sync_cst.ps1`，把工作区里新增或修改的 `*.py / *.md / *.docx / fig/*.png` 同步到 `cst/`。

## 4 提交粒度与信息

- 每完成一个可复现的单元就提交一次（建模脚本改完、一次对比跑完、一份报告定稿）
- 信息格式：`type(scope): 一句话`，type ∈ {feat, fix, data, docs, exp, chore}
  - 例：`exp(theory): 7 类远场模型 vs CST，RMSE 2.4-12.2 dB`
  - 例：`data(dataset): 49 例 20x20 随机码完成`
- 同一次实验的代码 + 配置 + 结果表放在**同一次提交**里

## 5 实时记录

- 每个工作日写一条 `docs/logs/YYYY-MM-DD.md`：做了什么、结论、待决事项
- 长跑任务（数据集生成）在日志里记录**开始/结束时间、样本数、失败样本**
- 交付给用户的结论，同步写入 `docs/` 下对应报告，避免只存在于对话中

## 6 推送

```powershell
git push origin main
```

远端：`git@github.com:XiaXiaXia-ai/metasurface-gnn.git`（SSH；https 为 `https://github.com/XiaXiaXia-ai/metasurface-gnn`）

首次推送已完成（2026-10-21）。`git config user.name = XiaXiaXia-ai`，提交作者与 GitHub 账号一致。）
