# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.results
import numpy as np
p = r"D:\cell_mesh\cell_bare.cst"
prj = cst.results.ProjectFile(p, allow_interactive=False)
r3 = prj.get_3d()
item = r3.get_result_item(r"1D Results\S-Parameters\SZmax(1),Zmax(1)")
rows = item.get_data()
x = np.array([r[0] for r in rows], float)
y = np.array([complex(r[1]) for r in rows])
print("npts", len(x), x.min(), x.max(), flush=True)
for f in (9.0, 9.5, 10.0, 10.5, 11.0):
    k = int(np.argmin(abs(x-f)))
    print("f=%.3f  |S|=%.6f  ph=%10.4f" % (x[k], abs(y[k]), np.degrees(np.angle(y[k]))), flush=True)
