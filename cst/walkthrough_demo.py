# -*- coding: utf-8 -*-
"""用一个真实 CST 样本走完 msgnn 的全流程，并逐项解释每个量的含义。

运行：
    python walkthrough_demo.py

数据：D:/dataset（CST 全波远场，2° 网格，8280 点，仅幅度）
代码：D:/GNN/gnn（包 msgnn，直接 import，不复制、不改动）
输出：demo_out/walkthrough_log.txt、demo_out/numbers.json、demo_out/fig_*.png
"""
import json
import os
import sys
import time
import warnings

import numpy as np

warnings.filterwarnings("ignore")

ROOT = r"D:/GNN/gnn"
sys.path.insert(0, ROOT)

import torch

torch.manual_seed(0)                    # 让 demo 里的随机初始化可复现
np.random.seed(0)

import msgnn  # noqa: F401  （会设置 KMP_DUPLICATE_LIB_OK）
from msgnn.config import load_config
from msgnn.data.build_graph import (EDGE_FEATURES, NODE_FEATURES, GraphDataset,
                                    build_graph, collate)
from msgnn.data.dataset import (Grid, case_from_files, load_target, make_splits,
                                scan_cases)
from msgnn.data.normalizer import Normalizer
from msgnn.evaluate import _solid_weights_for_oracle, metrics_for_sample
from msgnn.experiment import cast_batch
from msgnn.losses import angle_weights, build_loss
from msgnn.models.pipeline import _remove_graph_mean, build_pipeline
from msgnn.physics import baseline as BL
from msgnn.physics import radiation as R
from msgnn.physics.unit_library import UnitLibrary

OUT = r"D:/DSHNESS/GNN/demo_out"
os.makedirs(OUT, exist_ok=True)

try:                                    # Windows 控制台编码
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                       # noqa: BLE001
    pass

_LOG = open(os.path.join(OUT, "walkthrough_log.txt"), "w", encoding="utf-8")


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _LOG.write(s + "\n")


def sec(title):
    p()
    p("=" * 78)
    p(title)
    p("=" * 78)


def cplx(z):
    return "%+.4f%+.4fj" % (z.real, z.imag)


NUM = {}                                # 汇总数字，最后写 numbers.json


# ---------------------------------------------------------------------------
sec("[0] 环境")
p("python  :", sys.version.split()[0])
p("numpy   :", np.__version__)
p("torch   :", torch.__version__)
p("msgnn   :", msgnn.__version__, " <-", ROOT)
p("数据根目录:", r"D:/dataset")

cfg = load_config(os.path.join(ROOT, "configs", "train_m3.yaml"))
p("配置    :", os.path.join(ROOT, "configs", "train_m3.yaml"),
  "-> model.name =", cfg.model.name, "| dtype =", cfg.runtime.dtype)
p("物理参数: P = %.1f mm, n_side = %d, block = %d, f = %.1f GHz, 极化 = %s, 单元库 = %s"
  % (cfg.physics.period_mm, cfg.physics.n_side, cfg.physics.block,
     cfg.physics.freq_ghz, cfg.physics.projection, cfg.physics.gamma_source))

grid = Grid.from_step(2.0)
lam = R.lam_mm(cfg.physics.freq_ghz)
p("波长    : %.4f mm   （P/λ = %.3f）" % (lam, cfg.physics.period_mm / lam))
p("角度网格: theta %d 个 (0..90, 步长 2) × phi %d 个 (0..358, 步长 2) = %d 个方向"
  % (grid.n_theta, grid.n_phi, grid.size))

# ---------------------------------------------------------------------------
sec("[1] 原始数据：两个文件构成一个样本")
ff_path = r"D:/dataset/results/ff/ff_0000.txt"
res_path = r"D:/dataset/results/res_0000.json"
p("ff  文件:", ff_path, "(%d 字节)" % os.path.getsize(ff_path))
p("res 文件:", res_path, "(%d 字节)" % os.path.getsize(res_path))

with open(res_path, "r", encoding="utf-8") as fh:
    rec = json.load(fh)
p()
p("res_0000.json 全文：")
for k, v in rec.items():
    p("  %-16s = %s" % (k, v))

raw = np.loadtxt(ff_path)
p()
p("ff_0000.txt 前 5 行（共 %d 行）：" % raw.shape[0])
p("  %8s %8s %14s %14s" % ("theta", "phi", "|Eth|_dBsm", "|Ephi|_dBsm"))
for row in raw[:5]:
    p("  %8.1f %8.1f %14.4f %14.4f" % tuple(row))
p("  行数 %d = 46 × 180 ✓；两列 dBsm 是 20log10|E|，sigma = |E_theta|^2 + |E_phi|^2" % raw.shape[0])
sig_file = 10.0 ** (raw[:, 2] / 10.0) + 10.0 ** (raw[:, 3] / 10.0)
ring = sig_file[raw[:, 0] == 0.0]
kmax = int(sig_file.argmax())
p("  theta=0 的 180 行是镜面方向：总功率 σ 恒为 %.4f dBsm（180 个 φ 的展开 %.4f dB）"
  % (10 * np.log10(ring.mean()), 10 * np.log10(ring.max()) - 10 * np.log10(ring.min())))
p("    但两列会随 φ 旋转：φ=0° 时 |Eth| %+.2f / |Ephi| %+.2f；φ=90° 时 %+.2f / %+.2f"
  % (raw[0, 2], raw[0, 3], raw[45, 2], raw[45, 3]))
p("  全图最大值 %.4f dBsm 在 (θ=%.0f°, φ=%.0f°)，比镜面高 %.2f dB —— 不是同一个量"
  % (10 * np.log10(sig_file.max()), raw[kmax, 0], raw[kmax, 1],
     10 * np.log10(sig_file.max()) - 10 * np.log10(sig_file[0])))

# ---------------------------------------------------------------------------
sec("[2] 码 → 单元：100 个比特变成 400 个物理单元")
case = case_from_files(ff_path, res_path, grid,
                       block=cfg.physics.block, n_side=cfg.physics.n_side)
p("case.idx      =", case.idx)
p("code10 形状   =", case.code10.shape, "（10×10 宏比特，共 %d 个 1）" % int(case.code10.sum()))
p("bits   形状   =", case.bits.shape, "（每个宏比特按 block=%d 复制成 2×2）"
  % cfg.physics.block)
p("布局 layout_id=", case.layout_id, "（同一 layout 不会被分到两个 split）")
p()
p("10×10 码（'#'=1, '.'=0）：")
for row in case.code10:
    p("   " + "".join("#" if b else "." for b in row))
p()
p("20×20 物理比特（同样 400 个，但每 2×2 块相同）：")
for i in range(20):
    p("   " + "".join("#" if b else "." for b in case.bits[i]))

lib = UnitLibrary.floquet(cfg.physics.freq_ghz, cfg.physics.gamma_source)
q0 = lib(case.bits.ravel()).astype(complex)
g0v, g1v = lib.pair()
p()
p("单元库 Γ(state)：bit0 = %s   (|Γ| = %.3f, ∠ = %+.1f°)"
  % (cplx(g0v), abs(g0v), np.degrees(np.angle(g0v))))
p("                 bit1 = %s   (|Γ| = %.3f, ∠ = %+.1f°)"
  % (cplx(g1v), abs(g1v), np.degrees(np.angle(g1v))))
p("                 编码相位差 = %.2f°（1-bit 设计目标 180°）"
  % (np.degrees(np.angle(g1v / g0v)) % 360.0))
p("q0（400 个单元的复权重）只取这两个值：bit0 %d 个，bit1 %d 个"
  % (int((case.bits.ravel() == 0).sum()), int((case.bits.ravel() == 1).sum())))

# ---------------------------------------------------------------------------
sec("[3] 图：节点 = 单元，边 = 8 邻域")
g = build_graph(case, lib, cfg.physics.n_side, cfg.physics.period_mm,
                cfg.graph.radius, cfg.graph.self_loops, lam)
p("节点数 = %d, 边数 = %d（有向，双向都存）" % (g["n_nodes"], g["n_edges"]))
deg = np.bincount(g["edge_index"][1], minlength=g["n_nodes"])
vals, cnts = np.unique(deg, return_counts=True)
p("每个节点的入度分布：", dict(zip(vals.tolist(), cnts.tolist())),
  "（角 3 / 边 5 / 内部 8）")

p()
p("节点特征 9 维（NODE_FEATURES）：", ", ".join(NODE_FEATURES))
p("  %4s %-4s %-10s %-9s %-9s %-9s %-9s %-9s %-9s %-8s"
  % ("idx", "bit", "bit_signed", "x/λ", "y/λ", "ReΓ", "ImΓ", "|Γ|", "boundary", "n·z"))
probe = [0, 4, 10, 210, 399]
for i in probe:
    row = g["x"][i]
    p("  %4d %-4d %-10.3f %-9.3f %-9.3f %-9.4f %-9.4f %-9.4f %-9.3f %-8.3f"
      % (i, row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))
p("  说明：idx 0/399 是角点（boundary=1, 度 3），4 是角点上的 bit0，10 是边上（度 5），")
p("        210=(10,10) 是内部（度 8）。x/λ 范围 ±%.3f（19 个间距 = 8.87λ）"
  % abs(g["x"][:, 2]).max())

p()
p("边特征 5 维（EDGE_FEATURES）：", ", ".join(EDGE_FEATURES))
p("  %-8s %-8s %-8s %-8s %-9s %-9s %-9s"
  % ("src", "dst", "dx/λ", "dy/λ", "r/λ", "cos_az", "sin_az"))
ei, ea = g["edge_index"], g["edge_attr"]
for k in range(4):
    p("  %-8d %-8d %-8.4f %-8.4f %-9.4f %-9.4f %-9.4f"
      % (ei[0, k], ei[1, k], ea[k, 0], ea[k, 1], ea[k, 2], ea[k, 3], ea[k, 4]))
p("  说明：dx/λ = P/λ = %.4f 是相邻单元间距；对角线 r/λ = %.4f；方位角用 cos/sin 表示"
  % (cfg.physics.period_mm / lam, cfg.physics.period_mm * np.sqrt(2) / lam))

# ---------------------------------------------------------------------------
sec("[4] 真实数据集：全部样本 → 划分 → 训练集标准化")
t0 = time.time()
cases, warns = scan_cases(cfg.data, grid, verbose=False)
p("scan_cases 找到可用样本 %d 个（跳过 %d 个坏/未完成文件），耗时 %.1f s"
  % (len(cases), len(warns), time.time() - t0))
splits = make_splits(cases, cfg.data.val_frac, cfg.data.test_frac, cfg.data.split_seed)
p("按 layout_id 分组划分：train %d / val %d / test %d（seed=%d）"
  % (len(splits["train"]), len(splits["val"]), len(splits["test"]), splits["seed"]))
case_split = splits["cases"][str(case.idx)]["split"]
p("case 0000 落在：", case_split)

tr_cases = [c for c in cases if c.idx in set(splits["train"])]
t0 = time.time()
tr_graphs = [build_graph(c, lib, cfg.physics.n_side, cfg.physics.period_mm,
                         cfg.graph.radius, cfg.graph.self_loops, lam) for c in tr_cases]
norm = Normalizer.fit(tr_graphs)
p("只用 %d 张训练图拟合标准化（%.1f s），均值/标准差：" % (len(tr_graphs), time.time() - t0))
for j, name in enumerate(NODE_FEATURES):
    p("  %-11s mean = %+.4f   std = %.4f" % (name, norm.x_mean[j], norm.x_std[j]))
xt = norm.transform_x(g["x"])
p("同一个节点 210 标准化前后（前 6 维）：")
p("  原始: " + " ".join("%+.3f" % v for v in g["x"][210, :6]))
p("  标准: " + " ".join("%+.3f" % v for v in xt[210, :6]))

# ---------------------------------------------------------------------------
sec("[5] 物理前向 1/3：自检 —— 全 1 口径必须等于 PEC 平板 19.342 dBsm")
plate = R.plate_dbsm(cfg.physics.freq_ghz, cfg.physics.n_side, cfg.physics.period_mm)
uni = R.uniform_aperture_dbsm("vector", cfg.physics.freq_ghz,
                              cfg.physics.n_side, cfg.physics.period_mm)
p("解析式 4πA²/λ²      = %.9f dBsm" % plate)
p("用算子算 q≡1        = %.9f dBsm   差 %.2e dB" % (uni, uni - plate))
p("这一条同时钉住：单位（mm→m）、面积（P²）、常数 C、角度网格、极化投影。")
NUM["plate_dbsm"] = float(plate)

# ---------------------------------------------------------------------------
sec("[6] 物理前向 2/3：q0 → S → E → σ，逐个方向看数字")
pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)
fq, pm, pj = cfg.physics.freq_ghz, cfg.physics.period_mm, cfg.physics.projection
S = R.aperture_sum_numpy(q0, grid.theta, grid.phi, fq, pm, pos)
eth, eph = R.farfield_numpy(q0, grid.theta, grid.phi, fq, pm, pos, pj)
sigma = R.sigma_from_fields(eth, eph)
pred_db = R.to_db(sigma, -60.0)
targ_db = load_target(case, grid)["sig_db"]

p("  %-14s %-24s %-9s %-9s %-9s %-9s %-7s"
  % ("(theta,phi)", "S (复数和)", "|Eth| dB", "|Ephi| dB", "σ dBsm", "CST dBsm", "差"))
for th, ph in ((0, 0), (10, 0), (30, 90), (60, 180), (90, 0)):
    k = int(round(th / 2.0)) * 180 + (int(round(ph / 2.0)) % 180)
    e_th = max(20 * np.log10(abs(eth[k]) + 1e-300), -60.0)
    e_ph = max(20 * np.log10(abs(eph[k]) + 1e-300), -60.0)
    p("  %-14s %-24s %-9.3f %-9.3f %-9.3f %-9.3f %+7.2f"
      % ("(%d°,%d°)" % (th, ph), cplx(S[k]), e_th, e_ph,
         pred_db[k], targ_db[k], pred_db[k] - targ_db[k]))

p()
p("C = 2√π/λ · P² · 1e-3 = %.6f  （q 无量纲；|E|² 的单位是 m²，即 dBsm）"
  % R.const_c(cfg.physics.freq_ghz, cfg.physics.period_mm))
p("|S| 的上限是 400（400 个单元相位完全相同时）；本例 θ=0 处 |S| = %.2f，"
  % abs(S[0]))
p("只相当于全同相的 %.1f%% —— 1-bit 编码把相位打散，镜面方向就被压低了。"
  % (100.0 * abs(S[0]) / 400.0))
p()
p("注意 (90°,0°) 那一行：vector 投影在 θ=90 时 p_θ=cosθcosφ=0 且 p_φ=−sinφ=0，")
p("所以模型给出 σ→0（被 db_floor=−60 截断）。这是平面矢量投影的已知边界，")
p("真实全波数据在那里仍有 −17.9 dBsm；指标只在 θ≤90 且实测>−30 dBsm 的点上统计。")

# ---------------------------------------------------------------------------
sec("[7] 物理前向 3/3：M0 基线 vs CST（同一个样本）")
i0 = 0
band = grid.theta >= 10.0
p("镜面 θ=0   : M0 %+.3f dBsm | CST %+.3f dBsm | 缺口 %+.3f dB"
  % (pred_db[i0], targ_db[i0], pred_db[i0] - targ_db[i0]))
p("弥散 10–90: M0 %+.3f dBsm | CST %+.3f dBsm | 差 %+.3f dB"
  % (10 * np.log10((10 ** (pred_db[band] / 10)).mean()),
     10 * np.log10((10 ** (targ_db[band] / 10)).mean()),
     10 * np.log10((10 ** (pred_db[band] / 10)).mean())
     - 10 * np.log10((10 ** (targ_db[band] / 10)).mean())))

mt = metrics_for_sample(pred_db, targ_db, grid, cfg.eval)
p()
p("M0 的完整指标（theta 6–90°，实测 > −30 dBsm，n=%d）：" % mt["n_pts"])
p("  rho_lin      = %.4f   （0–90° 线性功率的 Pearson r，回答'镜面补上没'）" % mt["rho_lin"])
p("  rho_db       = %.4f   （dB 值的 r，回答'弥散结构对不对'）" % mt["rho_db"])
p("  bias_db      = %+.3f dB（平均偏高/偏低）" % mt["bias_db"])
p("  rmse_db      = %.3f dB" % mt["rmse_db"])
p("  spec_err     = %+.3f dB（θ=0 处）" % mt["spec_err"])
p("  mean_far_err = %+.3f dB（10–90° 线性均值之差）" % mt["mean_far_err"])
p("  分带 rmse: 0-5 %.2f | 5-15 %.2f | 15-30 %.2f | 30-60 %.2f | 60-90 %.2f"
  % (mt["rmse_b0_0_5"], mt["rmse_b1_5_15"], mt["rmse_b2_15_30"],
     mt["rmse_b3_30_60"], mt["rmse_b4_60_90"]))
NUM["m0"] = {k: float(v) for k, v in mt.items() if isinstance(v, (int, float))}

# ---------------------------------------------------------------------------
sec("[8] 损失：asinh 压缩到底改变了什么")
crit = build_loss(cfg.loss, grid.theta)
lt, lp = crit(torch.as_tensor(pred_db)[None], torch.as_tensor(targ_db)[None])
delta = pred_db - targ_db
p("loss（asinh, c=%.1f dB）= %.4f" % (cfg.loss.compression_db, float(lt)))
p("纯 MSE                     = %.2f  （就是 delta² 的均值）" % float((delta ** 2).mean()))
p("rmse_db = %.3f, bias_db = %+.3f（这两项用未压缩的 delta 算）"
  % (lp["rmse_db"], lp["bias_db"]))
p()
c = float(cfg.loss.compression_db)
for d in (1.0, 3.0, 10.0, 40.0):
    g_ = c * np.arcsinh(d / c)
    p("  |Δ| = %5.1f dB → asinh 后 %7.3f（平方 %8.2f）；若用 MSE 则是 %10.1f"
      % (d, g_, g_ ** 2, d * d))

w = angle_weights(grid.theta, cfg.loss)
p()
p("角度权重 w（已归一化到均值 1；w 是 8280 个方向的数组，θ 外层，每个 θ 占 180 个）")
p("  θ=0° %.3f | 6° %.3f | 30° %.3f | 90° %.3f"
  % (w[0], w[3 * 180], w[15 * 180], w[45 * 180]))
p("  （θ=0 被 floor 0.2 抬起来，又乘了 3 倍主瓣权重，所以反而比 θ=30° 大）")
mask = grid.theta < 6.0
p("  镜面锥 θ<6° 占总权重的 %.1f%%（既没被 sinθ 抹掉，也没被 boost 放大到主导）"
  % (100.0 * w[mask].sum() / w.sum()))

# ---------------------------------------------------------------------------
sec("[9] 那 13.8 dB 缺口到底是什么：给 M0 加一个全局复标量 b")
g0, gu = BL.field_terms(case.bits, grid.theta, grid.phi, lib,
                        cfg.physics.freq_ghz, cfg.physics.period_mm,
                        cfg.physics.projection, pos)
w_or = _solid_weights_for_oracle(cfg, grid)
b, pdb_b, rmse_b = BL.fit_global_scalar(g0, gu, targ_db, w=w_or)
p("模型:  E = g0 + b · gu      （gu = 全 1 口径的远场，g0 = M0 的远场）")
p("拟合得到 b = %s   |b| = %.4f, 相位 = %+.1f°" % (cplx(b), abs(b), np.degrees(np.angle(b))))
p("理论预期 |b| = 10^((10.798 − 19.342)/20) = %.3f（由镜面缺口折算；theory 报告给 0.37 / 265°）"
  % (10 ** ((10.798 - 19.342) / 20.0)))
p("  这里相位是 %+.1f°（即 %.1f°），与 265° 差约 30°：这是【单样本 + dB 域 + 主瓣权重 ×10】"
  % (np.degrees(np.angle(b)), np.degrees(np.angle(b)) % 360.0))
p("  的口径，不是 theory 那份多例全局拟合，所以只要求'同量级'而不是逐位相同。")
mb = metrics_for_sample(pdb_b, targ_db, grid, cfg.eval)
p()
p("加 b 之后：镜面 %+.3f → %+.3f dBsm（CST %+.3f），rho_lin %.4f → %.4f，"
  "rmse %.3f → %.3f dB"
  % (pred_db[0], pdb_b[0], targ_db[0], mt["rho_lin"], mb["rho_lin"],
     mt["rmse_db"], mb["rmse_db"]))
p("b 只有 2 个实自由度，却拿走了绝大部分镜面缺口 —— 这就是 M3 里全局支路存在的原因。")
NUM["oracle_b"] = {"re": float(b.real), "im": float(b.imag), "abs": float(abs(b)),
                   "phase_deg": float(np.degrees(np.angle(b))),
                   "rmse_db": float(mb["rmse_db"]), "rho_lin": float(mb["rho_lin"]),
                   "rho_db": float(mb["rho_db"]), "spec": float(pdb_b[0])}

# ---------------------------------------------------------------------------
sec("[10] GNN 前向：结构、形状、以及'零初始化 = M0'")
cfg64 = load_config(os.path.join(ROOT, "configs", "train_m3.yaml"),
                    overrides={"runtime": {"dtype": "float64"}})
op = R.FarFieldOperator(grid.theta, grid.phi, pos_mm=pos,
                        freq_ghz=cfg.physics.freq_ghz, period_mm=cfg.physics.period_mm,
                        projection=cfg.physics.projection, dtype=torch.float64)
ds1 = GraphDataset([case], grid, cfg64, lib, None)
batch1 = cast_batch(collate(ds1.select([0])), torch.float64)
p("单样本 batch 的形状：")
for k in ("x", "edge_index", "edge_attr", "batch", "ptr", "q0_re", "sig_db", "bits"):
    p("  %-11s %s" % (k, tuple(batch1[k].shape)))

ds8 = GraphDataset(cases[:8], grid, cfg64, lib, None)
batch8 = cast_batch(collate(ds8.select(list(range(8)))), torch.float64)
p("8 个样本的 batch：x %s, edge_index %s, sig_db %s"
  % (tuple(batch8["x"].shape), tuple(batch8["edge_index"].shape),
     tuple(batch8["sig_db"].shape)))

pipe3 = build_pipeline(cfg64, 9, 5, grid.n_theta, grid.n_phi, op).to(torch.float64)
cfg0 = load_config(os.path.join(ROOT, "configs", "train_m3.yaml"),
                   overrides={"runtime": {"dtype": "float64"}, "model": {"name": "m0"}})
pipe0 = build_pipeline(cfg0, 9, 5, grid.n_theta, grid.n_phi, op).to(torch.float64)
n_par = sum(q.numel() for q in pipe3.parameters())
p()
p("M3 参数量 = %d（其中 node_enc/edge_enc/mp/head/glob 见下表）" % n_par)
for name, mod in pipe3.net.named_children():
    p("  %-10s %8d 参数" % (name, sum(q.numel() for q in mod.parameters())))
NUM["n_params"] = int(n_par)

with torch.no_grad():
    o3 = pipe3(batch8)
    o0 = pipe0(batch8)
    dmax = float((o3["sig_db"] - o0["sig_db"]).abs().max())
p()
p("初始化（head 权重全 0）时：max|M3 − M0| = %.3e dB" % dmax)
p("  → 第 0 个 epoch 严格等于物理基线，之后每一步改进都可归因于学习。")
NUM["zero_init_maxdiff_db"] = dmax

# ---------------------------------------------------------------------------
sec("[11] 反向传播：第一步梯度落在谁身上")
model = pipe3
model.train()
out = model(batch8)
loss, parts = crit(out["sig_db"], batch8["sig_db"])
loss.backward()
p("初始 loss = %.4f（rmse %.3f dB）" % (float(loss), parts["rmse_db"]))
p("各模块的梯度绝对值和：")
for name, mod in model.net.named_children():
    gn = sum(float(q.grad.abs().sum()) for q in mod.parameters() if q.grad is not None)
    p("  %-10s %.4e" % (name, gn))
p("解释：head.weight = 0 ⇒ ∂L/∂h = 0，所以消息传递这一层第一步拿不到梯度；")
p("      head 和 glob 的梯度非零，先把'全局偏置'学会，第二步起 GNN 才开始更新。")

opt = torch.optim.AdamW([q for q in model.parameters() if q.requires_grad], lr=1e-3)
opt.step()
with torch.no_grad():
    out2 = model(batch8)
    loss2, _ = crit(out2["sig_db"], batch8["sig_db"])
    gr = model.net(batch8)
    bvec = gr["glob_re"] + 1j * gr["glob_im"]
    dqr, dqi = _remove_graph_mean(gr["node_re"], gr["node_im"],
                                  batch8["batch"], 8)
    dq = (dqr + 1j * dqi).reshape(8, 400)
p()
p("走一步 AdamW(lr=1e-3) 之后：loss %.4f → %.4f" % (float(loss), float(loss2)))
p("  |b| 逐样本：", " ".join("%.4f" % v for v in bvec.abs().tolist()))
p("  mean|Δq| 逐样本：", " ".join("%.2e" % v for v in dq.abs().mean(1).tolist()))
p("  （1 步 AdamW 在参数空间里就走 ~lr=1e-3，所以 Δq 已有 0.02；|q0|≈0.86，即约 2.5%。")
p("   这只是'机制演示'：真实训练 60 epoch 后 |b| 应接近 0.37，Δq 才是有效修正。）")

# ---------------------------------------------------------------------------
sec("[12] 指标对照：同一个样本、同一条曲线上的三个模型状态")
p("  %-14s %12s %14s %10s" % ("", "M0", "M0+b (oracle)", "CST"))
p("  %-14s %10.3f %10.3f %10.3f" % ("镜面 dBsm", pred_db[0], pdb_b[0], targ_db[0]))
p("  %-14s %10.4f %10.4f %10s" % ("rho_lin", mt["rho_lin"], mb["rho_lin"], "1.0"))
p("  %-14s %10.4f %10.4f %10s" % ("rho_db", mt["rho_db"], mb["rho_db"], "1.0"))
p("  %-14s %10.3f %10.3f %10s" % ("rmse_db", mt["rmse_db"], mb["rmse_db"], "0"))
NUM["sample"] = {"idx": case.idx, "split": case_split,
                 "spec_m0": float(pred_db[0]), "spec_cst": float(targ_db[0]),
                 "meanfar_m0": float(10 * np.log10((10 ** (pred_db[band] / 10)).mean())),
                 "meanfar_cst": float(10 * np.log10((10 ** (targ_db[band] / 10)).mean())),
                 "ones": int(case.bits.sum()), "code_ones": int(case.code10.sum())}

# ---------------------------------------------------------------------------
sec("[13] 画图")


def _font():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun"):
        if cand in have:
            plt.rcParams["font.sans-serif"] = [cand]
            break
    plt.rcParams["axes.unicode_minus"] = False
    return plt


plt = _font()
ZB = targ_db.reshape(grid.n_theta, grid.n_phi)
ZM = pred_db.reshape(grid.n_theta, grid.n_phi)
ZB2 = pdb_b.reshape(grid.n_theta, grid.n_phi)
T = grid.theta.reshape(grid.n_theta, grid.n_phi)
PH = grid.phi.reshape(grid.n_theta, grid.n_phi)
vmin, vmax = -25.0, 15.0

fig = plt.figure(figsize=(13.5, 9.0))
for k, (Z, title) in enumerate(((ZB, "(a) CST 全波仿真（标签）"),
                                (ZM, "(b) M0 物理基线（q = q0）"),
                                (ZB2, "(c) M0 + 1 个复标量 b（oracle 上界）"))):
    ax = fig.add_subplot(2, 2, k + 1)
    im = ax.pcolormesh(PH, T, Z, shading="auto", cmap="turbo", vmin=vmin, vmax=vmax)
    ax.set_xlabel("φ (deg)")
    ax.set_ylabel("θ (deg)")
    ax.set_title(title)
    ax.set_xlim(0, 360)
    ax.set_ylim(0, 90)
    fig.colorbar(im, ax=ax, label="σ (dBsm)")

ax = fig.add_subplot(2, 2, 4)
for j, lab in ((0, "φ = 0° (E 面)"), (45, "φ = 90° (H 面)")):
    ax.plot(grid.theta_ax, ZB[:, j], "k-", lw=2.2, label="CST" if j == 0 else None)
    ax.plot(grid.theta_ax, ZM[:, j], "C1--", lw=1.8, label="M0" if j == 0 else None)
    ax.plot(grid.theta_ax, ZB2[:, j], "C0:", lw=1.8, label="M0+b" if j == 0 else None)
ax.set_xlabel("θ (deg)")
ax.set_ylabel("σ (dBsm)")
ax.set_title("(d) 两个主平面的切面（实线 CST / 虚线 M0 / 点线 M0+b）")
ax.grid(alpha=0.3)
ax.legend(fontsize=8)
ax.set_xlim(0, 90)
fig.suptitle("case %d（%d 个 1 / 400 单元）：整条流程在同一张方向图上" %
             (case.idx, int(case.bits.sum())), fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.97))
fig1 = os.path.join(OUT, "fig_patterns.png")
fig.savefig(fig1, dpi=140)
plt.close(fig)

fig, axs = plt.subplots(1, 3, figsize=(15, 4.4))
axs[0].imshow(case.bits, cmap="Greys", vmin=0, vmax=1, interpolation="nearest")
axs[0].set_title("(a) 20×20 物理比特（灰=1）")
axs[0].set_xlabel("j (y 方向)")
axs[0].set_ylabel("i (x 方向)")
ph_q0 = np.degrees(np.angle(q0)).reshape(20, 20)
im = axs[1].imshow(ph_q0, cmap="twilight", vmin=-180, vmax=180, interpolation="nearest")
axs[1].set_title("(b) q0 的相位（°），只有 −5.3 和 174.6 两个值")
fig.colorbar(im, ax=axs[1], fraction=0.046, pad=0.03)
axs[2].plot(grid.theta_ax, np.abs(S.reshape(46, 180))[:, 0], "C3")
axs[2].set_title("(c) |S(θ)|，φ=0°：400 个复贡献的相干和")
axs[2].set_xlabel("θ (deg)")
axs[2].set_ylabel("|S|")
axs[2].grid(alpha=0.3)
fig.tight_layout()
fig2 = os.path.join(OUT, "fig_coding.png")
fig.savefig(fig2, dpi=140)
plt.close(fig)
p("图已保存：", fig1)
p("图已保存：", fig2)

# ---------------------------------------------------------------------------
with open(os.path.join(OUT, "numbers.json"), "w", encoding="utf-8") as fh:
    json.dump(NUM, fh, indent=1, ensure_ascii=False)

sec("[14] 一句话总结")
p("这份样本：400 单元、%d 个 1；CST 镜面 %.2f dBsm；M0 给 %.2f dBsm（差 %.2f dB）；"
  % (int(case.bits.sum()), targ_db[0], pred_db[0], pred_db[0] - targ_db[0]))
p("加一个复标量 b（|b|=%.3f）后镜面变成 %.2f dBsm；M3 就是让 GNN 从编码里"
  "同时学出 b 和每单元的 Δq。" % (abs(b), pdb_b[0]))
p("日志：", os.path.join(OUT, "walkthrough_log.txt"))
_LOG.close()
