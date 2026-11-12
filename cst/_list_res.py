# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.results
p = r"D:\re_cst_code1110\code1110_on.cst"
prj = cst.results.ProjectFile(p, allow_interactive=False)
r3 = prj.get_3d()
names = r3._get_all_result_items()
print("n", len(names))
for n in names:
    print(n)
