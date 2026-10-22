# -*- coding: utf-8 -*-
"""Batched inference over a GraphDataset (shared by train / evaluate / predict)."""
from typing import Dict, List, Optional, Sequence

import numpy as np
import torch

from .data.build_graph import GraphDataset, collate


@torch.no_grad()
def predict_dataset(model, ds: GraphDataset, indices: Optional[Sequence[int]] = None,
                    batch_size: int = 16, device: str = "cpu",
                    dtype=None) -> Dict[str, np.ndarray]:
    model.eval()
    order = list(range(len(ds))) if indices is None else [int(i) for i in indices]
    preds: List[np.ndarray] = []
    for s in range(0, len(order), batch_size):
        chunk = order[s:s + batch_size]
        batch = collate(ds.select(chunk))
        if dtype is not None:
            batch = {k: (v.to(dtype) if isinstance(v, torch.Tensor) and v.is_floating_point()
                         else v) for k, v in batch.items()}
        batch = _to_device(batch, device)
        out = model(batch)
        preds.append(out["sig_db"].detach().cpu().numpy().astype(np.float32))
    pred = np.concatenate(preds, axis=0) if preds else np.zeros((0, ds.grid.size))
    targ = ds.target_db.numpy()[order]
    return {"pred_db": pred, "targ_db": targ,
            "case_idx": np.array([ds.cases[i].idx for i in order], dtype=np.int64),
            "names": [ds.cases[i].name for i in order]}


def _to_device(batch: dict, device: str) -> dict:
    if device in (None, "cpu"):
        return batch
    out = {}
    for k, v in batch.items():
        out[k] = v.to(device) if isinstance(v, torch.Tensor) else v
    return out


@torch.no_grad()
def predict_q(model, batch: dict) -> Dict[str, np.ndarray]:
    """Return the per-node complex weights of a physics model for one batch."""
    q_re, q_im = model.q_of(batch)
    return {"q": (q_re.detach().cpu().numpy()
                  + 1j * q_im.detach().cpu().numpy())}
