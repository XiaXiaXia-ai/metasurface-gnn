# -*- coding: utf-8 -*-
"""Rebuild dataset case 0000 (20x20) as a SAVED project and leave it open in CST."""
import random
import sys
import time

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

import r42r5_dataset as R


def main():
    # must match the dataset configuration: 20x20 cells, 2x2 macro
    R.N = 20
    R.NB = 10
    R.L = 20 * R.P
    R.half = R.L / 2.0

    rng = random.Random(99500 + 0)
    bits = [[rng.randint(0, 1) for _ in range(10)] for _ in range(10)]
    code = [[bits[m // 2][n // 2] for n in range(20)] for m in range(20)]
    print("code (10x10 macro):", "".join("".join(str(b) for b in r) for r in bits))

    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    de.set_quiet_mode(True)
    prj = de.new_mws()
    time.sleep(0.5)
    R.build_case(prj, code)
    m = prj.model3d
    m.add_to_history("mesh", "Mesh.Update", timeout=1800)
    print("cells:", m.Mesh.GetNumberOfMeshCells())
    out = r"D:\dataset_r42r5_20\view_case0000.cst"
    prj.save(out, include_results=False, allow_overwrite=True)
    print("saved and left OPEN:", out)


if __name__ == "__main__":
    main()
