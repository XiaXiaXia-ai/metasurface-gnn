
import numpy as np
d = np.load(r"D:\DSHNESS\GNN\demo_out\diagnose_test.npz", allow_pickle=True)
print("keys:", list(d.keys()))
dq = d["dq_std"]; b = d["b"]; spec=d["spec"]; sc=d["spec_cst"]; bo=d["b_oracle"]
print("n =", dq.size)
print("std(Δq)  : mean %.4f  std %.4f  min %.4f  max %.4f" % (dq.mean(), dq.std(), dq.min(), dq.max()))
print("|b|      : mean %.4f  std %.4f   (theory 0.37)" % (np.abs(b).mean(), np.abs(b).std()))
print("|b|/std(Δq) median: %.2f" % np.median(np.abs(b)/np.maximum(dq,1e-9)))
print("corr(|b_learned|,|b_oracle|) = %.3f" % np.corrcoef(np.abs(b), np.abs(bo))[0,1])
print("spec err: mean %+0.3f  rmse %.3f" % ((spec-sc).mean(), np.sqrt(((spec-sc)**2).mean())))
# 相对量：q0 的幅度约 0.86
print("\n相对强度: std(Δq)/|q0| = %.2f%%" % (100*dq.mean()/0.86))
print("相对强度: |b|/|q0|      = %.2f%%" % (100*np.abs(b).mean()/0.86))
