# -*- coding: utf-8 -*-
"""诊断：训练后 M3 到底学到了什么（b、Δq、镜面）。

    python diagnose_demo.py

背景：msgnn/predict.py 在单样本时把 out["q_re"][0] 当成整条向量，实际拿到的是
标量（B=1 时 q_re 没有被 reshape 成 (1,N)），所以它打印的 |dq|/mean(dq) 不可信。
本脚本直接从模型取 q（形状 (N,)），按 q = q0 + Δq + b 拆开统计。
"""
import os
import sys

import numpy as np

sys.path.insert(0, r"D:/GNN/gnn")

import torch  # noqa: E402

from msgnn.config import load_config                    # noqa: E402
from msgnn.data.build_graph import collate              # noqa: E402
from msgnn.data.dataset import Grid, load_splits        # noqa: E402
from msgnn.experiment import build_context, build_model, cast_batch  # noqa: E402

RUN = r"D:/DSHNESS/GNN/demo_out/run_m3_demo"
OUT = r"D:/DSHNESS/GNN/demo_out"

cfg = load_config(os.path.join(RUN, "config.yaml"))
splits = load_splits(os.path.join(RUN, "splits.json"))
ctx = build_context(cfg, out_dir=RUN, splits=splits, save=False, verbose=False)
model = build_model(ctx)
ck = torch.load(os.path.join(RUN, "best.pt"), map_location="cpu")
model.load_state_dict(ck["model"])
model.eval()

ds = ctx.ds["test"]
rows = []
with torch.no_grad():
    for k in range(len(ds)):
        batch = cast_batch(collate(ds.select([k])), ctx.dtype, ctx.device)
        q_re, q_im = model.q_of(batch)
        q = (q_re.cpu().numpy() + 1j * q_im.cpu().numpy()).ravel()
        q0 = batch["q0"].cpu().numpy().ravel()
        b = (q - q0).mean()                 # Δq 已被去均值 ⇒ mean(q-q0) 就是 b
        dq = q - q0 - b
        sig = model(batch, return_fields=True)["sig_db"].cpu().numpy().ravel()
        rows.append(dict(case=ds.cases[k].idx, b_re=b.real, b_im=b.imag,
                         b_abs=abs(b), b_ph=np.degrees(np.angle(b)),
                         dq_std=float(np.abs(dq).std()),
                         dq_mean_abs=float(np.abs(dq).mean()),
                         spec=float(sig[0]),
                         spec_cst=float(ds.target_db[k].numpy()[0])))

b_abs = np.array([r["b_abs"] for r in rows])
b_ph = np.array([r["b_ph"] for r in rows])
dq_std = np.array([r["dq_std"] for r in rows])
spec = np.array([r["spec"] for r in rows])
spec_cst = np.array([r["spec_cst"] for r in rows])
spec_err = spec - spec_cst

print("[test split] %d 例" % len(rows))
print("|b|        : mean %.4f  std %.4f  min %.4f  max %.4f   （theory 0.37）"
      % (b_abs.mean(), b_abs.std(), b_abs.min(), b_abs.max()))
print("arg b (deg): mean %+.1f  std %.1f                  （theory 265°）"
      % (b_ph.mean(), b_ph.std()))
print("std(Δq)    : mean %.4f  （逐单元修正的强度）" % dq_std.mean())
print("|Δq| mean  : mean %.4f  （≈ std，因为均值为 0）"
      % np.mean([r["dq_mean_abs"] for r in rows]))
print("镜面 pred  : mean %.3f dBsm, 误差 mean %+.3f  rmse %.3f  （CST mean %.3f）"
      % (spec.mean(), spec_err.mean(), np.sqrt((spec_err ** 2).mean()), spec_cst.mean()))

# 和 M0+b oracle 对比：用同样的 |b| 但逐例拟合
import msgnn.physics.baseline as BL                       # noqa: E402
from msgnn.evaluate import _solid_weights_for_oracle      # noqa: E402
from msgnn.physics import radiation as R                  # noqa: E402

w = _solid_weights_for_oracle(cfg, ctx.grid)
pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)
b_or = []
for k, c in enumerate(ds.cases):
    g0, gu = BL.field_terms(c.bits, ctx.grid.theta, ctx.grid.phi, ctx.library,
                            cfg.physics.freq_ghz, cfg.physics.period_mm,
                            cfg.physics.projection, pos)
    bk, _, _ = BL.fit_global_scalar(g0, gu, ds.target_db[k].numpy(), w=w)
    b_or.append(bk)
b_or = np.array(b_or)
print("oracle |b| : mean %.4f  std %.4f" % (np.abs(b_or).mean(), np.abs(b_or).std()))

# 学到的 b 与 oracle b 的相关性
corr = np.corrcoef(b_abs, np.abs(b_or))[0, 1]
print("corr(|b_learned|, |b_oracle|) = %.3f" % corr)

np.savez(os.path.join(OUT, "diagnose_test.npz"),
         case=np.array([r["case"] for r in rows]),
         b=np.array([r["b_re"] + 1j * r["b_im"] for r in rows]),
         b_oracle=b_or, dq_std=dq_std, spec=spec, spec_cst=spec_cst)
print("saved:", os.path.join(OUT, "diagnose_test.npz"))
