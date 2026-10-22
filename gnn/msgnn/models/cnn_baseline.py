# -*- coding: utf-8 -*-
"""M1: CNN / U-Net style direct regression of the fixed far-field grid.

This is the control model of the plan (step 08, 'M1 CNN/U-Net directly predicts
the far-field on a fixed angular grid').  It sees only the 20x20 bit map and has
no physical operator, no unit-cell library and no graph:

    20x20 bits -> zero pad to 32x32 -> encoder (32/16/8/4) -> decoder with skips
                -> rank-r factorised read-out -> sigma_dB on the 46x180 grid

The read-out is factorised (A[nt,32] @ G[32,32] @ B[32,nphi]) instead of a dense
8280-way linear layer: same expressive family for a smooth 2-D pattern, a factor
~8 fewer parameters, and much faster on CPU.  A learnable 'sky' bias (the mean
pattern) is added, which is standard practice for limited-data pattern regression.

The output is sigma in dBsm, so it is scored by exactly the same loss and the
same metrics as M2/M3 (the comparison is then about the model, not the loss).
"""
from typing import Optional

import torch
import torch.nn as nn

from .encoders import make_act


def _conv(cin: int, cout: int, k: int = 3, stride: int = 1) -> nn.Module:
    pad = k // 2
    return nn.Conv2d(cin, cout, k, stride=stride, padding=pad)


class CNNBaseline(nn.Module):
    def __init__(self, n_side: int = 20, n_theta: int = 46, n_phi: int = 180,
                 width: int = 16, rank: int = 4, act: str = "gelu",
                 dropout: float = 0.0, pad: int = 32, bias_init: float = -20.0):
        super().__init__()
        self.n_side, self.nt, self.nph = n_side, n_theta, n_phi
        self.pad = pad
        w = width
        self.enc1 = nn.Sequential(_conv(1, w), make_act(act), _conv(w, w), make_act(act))
        self.enc2 = nn.Sequential(_conv(w, 2 * w, stride=2), make_act(act),
                                  _conv(2 * w, 2 * w), make_act(act))
        self.enc3 = nn.Sequential(_conv(2 * w, 4 * w, stride=2), make_act(act),
                                  _conv(4 * w, 4 * w), make_act(act))
        self.enc4 = nn.Sequential(_conv(4 * w, 4 * w, stride=2), make_act(act),
                                  _conv(4 * w, 4 * w), make_act(act))
        self.dec3 = nn.Sequential(_conv(8 * w, 2 * w), make_act(act))
        self.dec2 = nn.Sequential(_conv(4 * w, w), make_act(act))
        self.dec1 = nn.Sequential(_conv(2 * w, w), make_act(act))
        self.proj = nn.Conv2d(w, rank, 1)
        self.A = nn.Parameter(torch.empty(n_theta, pad))
        self.B = nn.Parameter(torch.empty(n_phi, pad))
        with torch.no_grad():
            nn.init.normal_(self.A, std=pad ** -0.5)
            nn.init.normal_(self.B, std=pad ** -0.5)
        self.sky = nn.Parameter(torch.full((1, n_theta, n_phi), float(bias_init)))
        self.drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()
        self.out_scale = nn.Parameter(torch.ones(1))

    # ------------------------------------------------------------------ utils
    def _pad_bits(self, bits: torch.Tensor) -> torch.Tensor:
        b = bits.unsqueeze(1)                                   # (B,1,20,20)
        if self.pad == self.n_side:
            return b
        if self.pad < self.n_side:
            return b
        d = (self.pad - self.n_side) // 2
        return nn.functional.pad(b, (d, self.pad - self.n_side - d,
                                     d, self.pad - self.n_side - d))

    # ---------------------------------------------------------------- forward
    def forward(self, batch: dict) -> torch.Tensor:
        x = self._pad_bits(batch["bits"].float())
        e1 = self.enc1(x)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)
        u3 = nn.functional.interpolate(e4, size=e3.shape[-2:], mode="nearest")
        d3 = self.dec3(torch.cat([u3, e3], dim=1))
        u2 = nn.functional.interpolate(d3, size=e2.shape[-2:], mode="nearest")
        d2 = self.dec2(torch.cat([u2, e2], dim=1))
        u1 = nn.functional.interpolate(d2, size=e1.shape[-2:], mode="nearest")
        d1 = self.dec1(torch.cat([u1, e1], dim=1))
        f = self.proj(self.drop(d1))                            # (B, r, H, W)
        # (B,r,nt,nph) = A @ f @ B^T, applied per rank channel
        g = torch.einsum("th,brhw->brtw", self.A, f)            # (B,r,nt,W)
        z = torch.einsum("ph,brtw->brtp", self.B, g)            # (B,r,nt,nph)
        z = z.sum(dim=1)                                        # (B,nt,nph)
        out = self.out_scale * z + self.sky
        return out.reshape(out.shape[0], -1)

    def n_parameters(self) -> int:
        return int(sum(p.numel() for p in self.parameters()))
