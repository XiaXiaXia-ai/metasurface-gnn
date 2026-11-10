# -*- coding: utf-8 -*-
"""Independent 10x10 dataset, 1000 cases, stored in its own folder.

Same unit cell, substrate, 15 mm background, monitors and solver settings as the
12x12 / 16x16 / 20x20 sets, so all four are directly comparable.

    10 x 10 = 100 elements, 2x2 macro cells -> 5 x 5 = 25 bits
    array 140 x 140 mm, PEC reference 7.30 dBsm

    D:\\dataset10\\codes\\code_0000.txt
    D:\\dataset10\\results\\res_0000.json
    D:\\dataset10\\results\\ff\\ff_0000.txt
    D:\\dataset10\\progress.log / progress.jsonl

    python dataset10_gen.py --supervise 150
    python dataset10_gen.py --status
"""
import os
import sys

os.environ["META_DATASET_ROOT"] = r"D:\dataset10"
os.environ["META_DATASET_N"] = "10"
os.environ["META_DATASET_TOTAL"] = "1000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dataset_gen as D  # noqa: E402

if __name__ == "__main__":
    D.main()
