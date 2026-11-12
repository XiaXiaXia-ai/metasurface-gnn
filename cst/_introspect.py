# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.results
p = r"D:\re_cst_code1110\code1110_on.cst"
prj = cst.results.ProjectFile(p, allow_interactive=False)
print("PRJ attrs:", [a for a in dir(prj) if not a.startswith("__")])
r3 = prj.get_3d()
print("R3 attrs:", [a for a in dir(r3) if not a.startswith("__")])
