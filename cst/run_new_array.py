# -*- coding: utf-8 -*-
"""Rebuild the coding array with the new substrate/radii and solve it."""
import sys
import time

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

import build_coding_array as B

de = cst.interface.DesignEnvironment.connect_to_any()
prj = de.new_mws()
time.sleep(1.0)
m3d = prj.model3d

try:
    for caption, code in B.vba:
        t0 = time.time()
        try:
            m3d.add_to_history(caption, code, timeout=600)
        except Exception as exc:  # noqa: BLE001
            if caption in B.OPTIONAL_CAPTIONS:
                print("  [skip] %-45s %s" % (caption, str(exc).replace("\n", " ")[:90]), flush=True)
                continue
            raise
        print("  [ok] %-45s %.1fs" % (caption, time.time() - t0), flush=True)
except Exception:
    print("build failed -> project left open, not saved", flush=True)
    raise

prj.save(B.OUT, include_results=False, allow_overwrite=True)
print("saved:", B.OUT, flush=True)
print("solve start:", time.strftime("%H:%M:%S"), flush=True)
t0 = time.time()
m3d.run_solver()
print("solved in %.1f s" % (time.time() - t0), flush=True)
prj.save(include_results=True, allow_overwrite=True)
print("saved with results", flush=True)
