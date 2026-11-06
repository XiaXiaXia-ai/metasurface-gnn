# -*- coding: utf-8 -*-
"""Independent 16x16 dataset, 1000 cases, stored in its own folder.

Everything else (unit cell, substrate material, 15 mm background, monitors,
mesh rules, solver settings) is inherited from build_coding_array, so the
16x16 samples are directly comparable with the 20x20 set.

    D:\\dataset16\\codes\\code_0000.txt
    D:\\dataset16\\results\\res_0000.json
    D:\\dataset16\\results\\ff\\ff_0000.txt
    D:\\dataset16\\progress.log / progress.jsonl

Same resumable behaviour: re-running continues where it stopped.
    python dataset16_gen.py --supervise 150
    python dataset16_gen.py --status
"""
import os
import sys

os.environ["META_DATASET_ROOT"] = r"D:\dataset16"
os.environ["META_DATASET_N"] = "16"
os.environ["META_DATASET_TOTAL"] = "1000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dataset_gen as D  # noqa: E402

if __name__ == "__main__":
    D.main()
