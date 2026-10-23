
# -*- coding: utf-8 -*-
import os, sys
import numpy as np
sys.path.insert(0, r"D:/GNN/gnn")
import torch
from msgnn.config import load_config
from msgnn.data.build_graph import collate
from msgnn.data.dataset import load_splits
from msgnn.experiment import build_context, build_model, cast_batch

RUN = r"D:/DSHNESS/GNN/demo_out/run_m3_demo"
cfg = load_config(os.path.join(RUN, "config.yaml"))
splits = load_splits(os.path.join(RUN, "splits.json"))
ctx = build_context(cfg, out_dir=RUN, splits=splits, save=False, verbose=False)
model = build_model(ctx)
ck = torch.load(os.path.join(RUN, "best.pt"), map_location="cpu")
model.load_state_dict(ck["model"]); model.eval()

ds = ctx.ds["test"]; n = cfg.physics.n_side
DQ, BIT, NBM, CASEB = [], [], [], []
with torch.no_grad():
    for k in range(len(ds)):
        batch = cast_batch(collate(ds.select([k])), ctx.dtype, ctx.device)
        q_re, q_im = model.q_of(batch)
        q  = (q_re.cpu().numpy() + 1j*q_im.cpu().numpy()).ravel()
        q0 = batch["q0"].cpu().numpy().ravel()
        b  = (q - q0).mean()
        dq = q - q0 - b
        bits = ds.cases[k].bits.astype(float).reshape(n, n)
        nb = np.zeros((n, n)); cnt = np.zeros((n, n))
        for di in (-1,0,1):
            for dj in (-1,0,1):
                if di==0 and dj==0: continue
                i0,i1 = max(0,-di), min(n, n-di); j0,j1 = max(0,-dj), min(n,n-dj)
                nb[i0:i1, j0:j1] += bits[i0+di:i1+di, j0+dj:j1+dj]
                cnt[i0:i1, j0:j1] += 1
        DQ.append(dq); BIT.append(bits.ravel()); NBM.append((nb/cnt).ravel()); CASEB.append(b)

DQ = np.concatenate(DQ); BIT = np.concatenate(BIT); NBM = np.concatenate(NBM)
print("nodes: %d cases: %d" % (DQ.size, len(CASEB)))
print("|q0| = %.4f ; |b| mean %.4f std %.4f" % (np.abs(0.86), np.mean(np.abs(CASEB)), np.std(np.abs(CASEB))))
print("std(dq) = %.4f  mean|dq| = %.4f" % (DQ.std(), np.abs(DQ).mean()))

# 1) 按自身 bit 分组
for s in (0,1):
    m = BIT == s
    print("bit=%d  n=%6d  mean dq = %+.4f%+.4fj   std %+.4f  |dq| %.4f"
          % (s, m.sum(), DQ[m].real.mean(), DQ[m].imag.mean(), DQ[m].std(), np.abs(DQ[m]).mean()))

# 2) 去掉"每态常数"后还剩多少
res = DQ.copy()
for s in (0,1):
    m = BIT == s
    res[m] = DQ[m] - DQ[m].mean()
print("\n去掉每态均值后: std(res) = %.4f  (= %.1f%% of std(dq))  |res| %.4f"
      % (res.std(), 100*res.std()/DQ.std(), np.abs(res).mean()))

# 3) 残差与"邻居态占比"的相关
for part, name in ((res.real,"Re"), (res.imag,"Im")):
    c = np.corrcoef(part, NBM)[0,1]
    print("corr(%s(res), neighbor_bit_frac) = %+.4f" % (name, c))

# 4) 按 (自身bit, 邻居占比分箱) 看 Re(dq) 的走向
for s in (0,1):
    m = BIT == s
    print("\nbit=%d:" % s)
    for lo in np.arange(0, 1.0, 0.2):
        mm = m & (NBM >= lo) & (NBM < lo+0.2)
        if mm.sum() > 200:
            print("   nbr in [%.1f,%.1f): n=%6d  Re(dq)=%+.4f  Im(dq)=%+.4f"
                  % (lo, lo+0.2, mm.sum(), DQ[mm].real.mean(), DQ[mm].imag.mean()))
