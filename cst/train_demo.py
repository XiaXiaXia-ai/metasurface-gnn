# -*- coding: utf-8 -*-
"""演示用：真跑一次训练（5 epoch，只为展示链路，不是最终结果）。

    python train_demo.py

产物在 demo_out/run_m3_demo/：config/snapshot/splits/normalizer/best.pt/history.csv/summary.json
"""
import json
import os
import sys

sys.path.insert(0, r"D:/GNN/gnn")

from msgnn.config import load_config          # noqa: E402
from msgnn.train import train                # noqa: E402

OUT = r"D:/DSHNESS/GNN/demo_out/run_m3_demo"
cfg = load_config(r"D:/GNN/gnn/configs/train_m3.yaml")
print("[demo] model=%s epochs=5 (config says %d) -> %s"
      % (cfg.model.name, cfg.optim.epochs, OUT), flush=True)
summary = train(cfg, OUT, seed=0, epochs=5, verbose=True)
print(json.dumps(summary, indent=1, ensure_ascii=False), flush=True)
