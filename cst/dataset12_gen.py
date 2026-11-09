# -*- coding: utf-8 -*-
"""Independent 12x12 dataset, 1000 cases, stored in its own folder.

Same unit cell, substrate, 15 mm background, monitors and solver settings as the
16x16 and 20x20 sets, so the three are directly comparable.

    12 x 12 = 144 elements, 2x2 macro cells -> 6 x 6 = 36 bits
    array 168 x 168 mm, PEC reference 10.47 dBsm

    D:\\dataset12\\codes\\code_0000.txt
    D:\\dataset12\\results\\res_0000.json
    D:\\dataset12\\results\\ff\\ff_0000.txt
    D:\\dataset12\\progress.log / progress.jsonl

    python dataset12_gen.py --supervise 150
    python dataset12_gen.py --status
"""
import os
import sys

os.environ["META_DATASET_ROOT"] = r"D:\dataset12"
os.environ["META_DATASET_N"] = "12"
os.environ["META_DATASET_TOTAL"] = "1000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dataset_gen as D  # noqa: E402

if __name__ == "__main__":
    D.main()
