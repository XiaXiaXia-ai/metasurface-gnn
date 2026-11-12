# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.results
import numpy as np
for p in [r"D:\re_cst_code1110\code1110_m0.cst", r"D:\re_cst_code1110\code1110_m1.cst", r"D:\re_cst_code1110\code1110_on.cst"]:
    print("##", p)
    try:
        prj = cst.results.ProjectFile(p, allow_interactive=False)
        r3 = prj.get_3d()
        item = r3.get_result_item(r"1D Results\S-Parameters\SZmax(1),Zmax(1)")
        rows = item.get_data()
        x = np.array([r[0] for r in rows], float)
        y = np.array([complex(r[1]) for r in rows])
        db = 20*np.log10(np.abs(y)); ph = np.degrees(np.angle(y))
        k = int(np.argmin(abs(x-10)))
        print("  n=%d  range %.2f-%.2f  @10: |S|=%.4f dB ph=%.3f" % (len(x), x[0], x[-1], db[k], ph[k]))
        # min |S| and phase zero crossing
        km = int(np.argmin(db))
        print("  min|S| at %.3f GHz: %.4f dB, ph=%.2f" % (x[km], db[km], ph[km]))
        for f in (8.0, 9.0, 10.0, 11.0, 12.0):
            kk=int(np.argmin(abs(x-f))); print("   f=%.1f  %8.3f dB  %9.3f deg"%(x[kk],db[kk],ph[kk]))
    except Exception as e:
        print("  ERR", e)
