# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.results
import numpy as np
p = r"D:\re_cst_code1110\code1110_on.cst"
prj = cst.results.ProjectFile(p, allow_interactive=False)
r3 = prj.get_3d()
for name in [r"1D Results\Port Information\Gamma\Zmax(1)",
             r"1D Results\Port Information\Distance (-40 dB)\Zmax(1)",
             r"1D Results\Port Information\Effective Dielectric Constant\Zmax(1)",
             r"1D Results\Port Information\Wave Impedance\Zmax(1)",
             r"1D Results\Reference Impedance\ZRef Zmax(1)"]:
    try:
        item = r3.get_result_item(name)
        rows = item.get_data()
        print("##", name, "n=", len(rows))
        for row in rows[:4]:
            print("   ", row)
    except Exception as e:
        print("##", name, "ERR", e)
