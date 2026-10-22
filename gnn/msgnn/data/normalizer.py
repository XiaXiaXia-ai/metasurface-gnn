# -*- coding: utf-8 -*-
"""Feature normaliser fitted on the training split only.

Continuous node/edge features are standardised with the training mean and
standard deviation; geometry that the physics uses (positions in mm, q0, the
far-field target) is never rescaled.  Fitting is therefore a one-liner on the
training graphs, and the statistics are stored next to the checkpoint so a
prediction run reproduces them exactly (data-leakage guard required by the plan,
appendix A "防止数据泄漏").
"""
import json
from dataclasses import dataclass, asdict
from typing import Optional, Sequence

import numpy as np
import torch


@dataclass
class Normalizer:
    x_mean: Optional[list] = None
    x_std: Optional[list] = None
    e_mean: Optional[list] = None
    e_std: Optional[list] = None
    n_graphs: int = 0

    # ------------------------------------------------------------------- fit
    @classmethod
    def fit(cls, graphs: Sequence[dict]) -> "Normalizer":
        if not graphs:
            raise ValueError("cannot fit a normaliser on zero graphs")
        x = np.concatenate([np.asarray(g["x"], dtype=np.float64) for g in graphs], axis=0)
        e = [np.asarray(g["edge_attr"], dtype=np.float64) for g in graphs
             if np.asarray(g["edge_attr"]).size]
        e = np.concatenate(e, axis=0) if e else np.zeros((1, 1))
        return cls(x_mean=x.mean(0).tolist(),
                   x_std=_safe_std(x).tolist(),
                   e_mean=e.mean(0).tolist(),
                   e_std=_safe_std(e).tolist(),
                   n_graphs=len(graphs))

    # --------------------------------------------------------------- transform
    def transform_x(self, x) -> np.ndarray:
        if self.x_mean is None:
            return np.asarray(x, dtype=np.float32)
        m = np.asarray(self.x_mean, dtype=np.float64)
        s = np.asarray(self.x_std, dtype=np.float64)
        return ((np.asarray(x, dtype=np.float64) - m) / s).astype(np.float32)

    def transform_e(self, e) -> np.ndarray:
        e = np.asarray(e, dtype=np.float64)
        if self.e_mean is None or e.size == 0:
            return e.astype(np.float32)
        m = np.asarray(self.e_mean, dtype=np.float64)
        s = np.asarray(self.e_std, dtype=np.float64)
        return ((e - m) / s).astype(np.float32)

    # -------------------------------------------------------------- persistence
    def save(self, path: str) -> str:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=1)
        return path

    @classmethod
    def load(cls, path: str) -> "Normalizer":
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        return cls(**d)


def _safe_std(a: np.ndarray) -> np.ndarray:
    s = a.std(0)
    s[s < 1e-8] = 1.0
    return s


def to_tensor(a, dtype=torch.float32) -> torch.Tensor:
    return torch.as_tensor(np.ascontiguousarray(a), dtype=dtype)
