import pandas as pd, numpy as np
d = pd.read_csv(r"D:\GNN\theory\results.csv")
m = d[d.model != "MEASURED"].copy()
ref = d[d.model == "MEASURED"].set_index("case")
# merge measured values
m["d_spec"] = m.apply(lambda r: r.specular_dbsm - ref.loc[r.case, "specular_dbsm"], axis=1)
m["d_mean"] = m.apply(lambda r: r.mean_far_dbsm - ref.loc[r.case, "mean_far_dbsm"], axis=1)
f1 = m[m.case.str.startswith("ff_")]
g = f1.groupby("model").agg(rmse=("rmse_6_60deg", "mean"),
                            corr=("corr_phi0", "mean"),
                            absspec=("d_spec", lambda s: np.abs(s).mean()),
                            absmean=("d_mean", lambda s: np.abs(s).mean()))
g["score"] = g.rmse + g.absspec + g.absmean
print("=== 5 个 1 度频点上的平均（越小越好） ===")
print(g.sort_values("score").round(2).to_string())
print()
# per-case RMSE for the best few
sel = ["M1_AF+element", "M0_AF", "M0b_AF_vector", "M3_RS", "M6_phase_compress", "M2_PO_fitted"]
print(pd.pivot_table(f1[f1.model.isin(sel)], index="model", columns="case",
                     values="rmse_6_60deg").round(2).to_string())
print()
print(pd.pivot_table(f1[f1.model.isin(sel)], index="model", columns="case",
                     values="corr_phi0").round(2).to_string())
