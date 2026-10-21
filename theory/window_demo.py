# -*- coding: utf-8 -*-
"""window_demo.py -- what the two rho windows mean, decomposed by theta band."""
import numpy as np, pandas as pd
import common as C, models as M

g, eth, eph = C.load_ff6(C.DATA_1DEG % "10")
meas = C.total_db(eth, eph)
cm, _ = C.base_code_map()

WINDOWS = [("0-6", 0, 6), ("6-60", 6, 60), ("0-60", 0, 60), ("60-90", 60, 90),
           ("6-90", 6, 90), ("0-90", 0, 90)]

def rho(a, b, m):
    return np.corrcoef(a[m], b[m])[0, 1] if m.sum() > 5 else np.nan

rows = []
for lab, fn in (("M0_AF", lambda: M.af_ideal(g, 10.0, cm)),
                ("M1_AF+element", lambda: M.af_element(g, 10.0, cm, q=-0.396, scale=1.112)),
                ("M3_RS", lambda: M.rs_farfield(g, 10.0, cm)),
                ("M2_PO_fitted", lambda: M.po_two_region(g, 10.0, cm,
                                                          gamma_gap=0.628 * np.exp(1j * np.radians(142))))):
    db = fn().db
    rec = {"model": lab}
    for pc in (0, 90):
        cut = g.cut(pc)
        for tag, lo, hi in WINDOWS:
            m = cut & (g.th >= lo) & (g.th < hi) & (meas > -30)
            rec["%s_%d" % (tag, pc)] = (rho(db, meas, m), int(m.sum()))
    rows.append(rec)
df = pd.DataFrame(rows)
pd.set_option("display.width", 250)
for pc in (0, 90):
    print("\n=== phi = %d deg : Pearson r over different theta windows ===" % pc)
    out = pd.DataFrame({r["model"]: {w: "%.3f (n=%d)" % r["%s_%d" % (w, pc)] for w, _, _ in WINDOWS}
                        for r in rows})
    print(out.to_string())
