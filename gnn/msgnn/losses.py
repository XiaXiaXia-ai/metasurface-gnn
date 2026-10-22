# -*- coding: utf-8 -*-
"""Losses: 'power' (amplitude-only labels) and 'complex' (6-column labels).

Both share the same three ingredients required by the plan (appendix B):

  * solid-angle weights w ~ sin(theta), so a uniform (theta, phi) grid is not
    over-counted at the poles; a floor keeps the specular sample from getting
    exactly zero weight;
  * an optional main-lobe boost and an optional null-depth term;
  * dynamic-range compression, because the specular lobe is 25-30 dB above the
    diffuse floor and would otherwise own the gradient.

Power mode (default, matches the current dataset)
    delta = sigma_hat_dB - sigma_dB,     g(d) = c * asinh(d / c)
    L = sum_m w_m g(delta_m)^2 / (B * sum_m w_m)
    c = compression_db (3 dB by default): residuals well below c are quadratic,
    residuals above c grow only logarithmically.  'none' recovers plain MSE.

Complex mode (needs the 6-column export)
    L = sum_m w_m |F_hat_m - F_m|^2 / (|F_m|^2 + eps_rel * mean|F|^2) / sum w
    i.e. a per-direction relative error with an energy floor, which is the
    compressed version of the plan's formula
        sum w |F_hat - F|^2 / (sum w |F|^2 + eps).
    With complex_compress = False the plan's energy-normalised form is used.
"""
from typing import Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

from .config import LossCfg


def angle_weights(theta_deg, cfg: LossCfg) -> np.ndarray:
    """(M,) positive weights, mean 1."""
    t = np.asarray(theta_deg, dtype=float).ravel()
    if cfg.angle_weight == "uniform":
        w = np.ones_like(t)
    elif cfg.angle_weight == "solid_angle":
        w = np.sin(np.radians(t)) + float(cfg.weight_floor)
    else:
        raise ValueError("angle_weight must be uniform or solid_angle")
    if cfg.mainlobe_boost != 1.0:
        w = w * np.where(t < cfg.mainlobe_deg, float(cfg.mainlobe_boost), 1.0)
    w = w / w.mean()
    return w.astype(np.float64)


class PowerLoss(nn.Module):
    """dB-domain loss for amplitude-only labels."""

    def __init__(self, cfg: LossCfg, theta_deg, clip_db: float = 80.0):
        super().__init__()
        self.cfg = cfg
        w = torch.as_tensor(angle_weights(theta_deg, cfg), dtype=torch.float32)
        self.register_buffer("w", w)
        self.clip_db = float(clip_db)

    def _compress(self, d: torch.Tensor) -> torch.Tensor:
        if self.cfg.compression == "none":
            return d
        c = float(self.cfg.compression_db)
        return c * torch.asinh(d / c)

    def forward(self, pred_db: torch.Tensor, targ_db: torch.Tensor
                ) -> Tuple[torch.Tensor, Dict[str, float]]:
        b, m = pred_db.shape
        w = self.w.to(dtype=pred_db.dtype, device=pred_db.device)[None, :]
        delta = (pred_db - targ_db).clamp(-self.clip_db, self.clip_db)
        g = self._compress(delta)
        loss = (w * g * g).sum() / (w.sum() * b + 1e-12)
        parts = {}
        nl = None
        if self.cfg.null_weight > 0:
            # optional extra term that only looks at the deep (null) region
            top = targ_db.max(dim=1, keepdim=True).values
            mask = (targ_db < top - float(self.cfg.null_depth_db)).to(pred_db.dtype)
            nl = (w * mask * g * g).sum() / (w * mask).sum().clamp_min(1.0)
            loss = loss + float(self.cfg.null_weight) * nl
        with torch.no_grad():
            parts["rmse_db"] = float(torch.sqrt((w * delta * delta).sum()
                                                / (w.sum() * b)))
            parts["bias_db"] = float((w * delta).sum() / (w.sum() * b))
            if nl is not None:
                parts["null"] = float(nl)
        parts["loss"] = float(loss)
        return loss, parts


class ComplexLoss(nn.Module):
    """Relative complex-field loss with an optional per-angle compression."""

    def __init__(self, cfg: LossCfg, theta_deg):
        super().__init__()
        self.cfg = cfg
        w = torch.as_tensor(angle_weights(theta_deg, cfg), dtype=torch.float32)
        self.register_buffer("w", w)

    def forward(self, pred: Dict[str, torch.Tensor], targ: Dict[str, torch.Tensor]
                ) -> Tuple[torch.Tensor, Dict[str, float]]:
        w = self.w.to(dtype=pred["eth_re"].dtype,
                     device=pred["eth_re"].device)[None, :]
        er = pred["eth_re"] - targ["eth_re"]
        ei = pred["eth_im"] - targ["eth_im"]
        pr = pred["eph_re"] - targ["eph_re"]
        pi_ = pred["eph_im"] - targ["eph_im"]
        num = er * er + ei * ei + pr * pr + pi_ * pi_
        tr = targ["eth_re"] ** 2 + targ["eth_im"] ** 2 + targ["eph_re"] ** 2 + targ["eph_im"] ** 2
        if self.cfg.complex_compress:
            a2 = (w * tr).sum(dim=1, keepdim=True) / w.sum()
            e_m = tr + float(self.cfg.eps_rel) * a2
            loss = (w * num / e_m.clamp_min(1e-30)).sum() / w.sum()
        else:
            loss = (w * num).sum() / ((w * tr).sum() + float(self.cfg.eps_rel))
        parts = {"loss": float(loss)}
        with torch.no_grad():
            parts["rel_l2"] = float(num.sum() / (tr.sum() + 1e-30))
        return loss, parts


def build_loss(cfg: LossCfg, theta_deg):
    if cfg.mode == "power":
        return PowerLoss(cfg, theta_deg)
    if cfg.mode == "complex":
        return ComplexLoss(cfg, theta_deg)
    raise ValueError("loss.mode must be power or complex")
