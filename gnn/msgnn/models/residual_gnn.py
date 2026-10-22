# -*- coding: utf-8 -*-
"""M2 / M3 graph networks: per-node complex source coefficients.

M2 (direct)      q_n = head(h_n)
M3 (residual)    q_n = q0_n + dq_n + b            (q0 from the unit-cell library)
                 b   = per-sample complex common mode produced by the global branch

The residual form is the one recommended by the plan (step 07) and by
theory/REPORT.md sec. 7: the local-periodic solution is already right in
structure, so the network only has to learn a correction.  The optional global
branch adds ONE complex number per sample that is shared by every node -- this is
exactly the 'code-orthogonal uniform common mode' of the attribution report
(|b| = 0.37, phase 265 deg), and it is the cheapest possible correction: 2 real
degrees of freedom instead of 800.

A zero-initialised head makes M3 start exactly at the M0 baseline (dq = 0, b = 0),
so the first epoch is 'M0' and every bit of improvement afterwards is learned.
"""
from typing import Optional

import torch
import torch.nn as nn

from .encoders import MLP, NodeEncoder, EdgeEncoder, count_parameters
from .message_passing import MessagePassingStack


class GraphNet(nn.Module):
    """Node/edge encoders -> message passing -> complex per-node coefficients."""

    def __init__(self, node_dim: int, edge_dim: int, hidden: int = 64,
                 n_layers: int = 3, act: str = "gelu", layer_norm: bool = True,
                 dropout: float = 0.0, global_branch: bool = True,
                 direct: bool = False, zero_init_head: bool = True,
                 aggr: str = "sum", edge_emb_dim: Optional[int] = None):
        super().__init__()
        self.direct = bool(direct)
        self.global_branch = bool(global_branch)
        self.edge_dim = int(edge_dim)
        he = int(edge_emb_dim if edge_emb_dim is not None else hidden)
        self.edge_emb_dim = he if self.edge_dim > 0 else 0

        self.node_enc = NodeEncoder(node_dim, hidden, act=act, layers=2,
                                    layer_norm=layer_norm, dropout=dropout)
        self.edge_enc = (EdgeEncoder(self.edge_dim, self.edge_emb_dim, act=act,
                                     layers=2, dropout=dropout)
                         if self.edge_dim > 0 else None)
        self.mp = MessagePassingStack(n_layers, hidden, self.edge_emb_dim, act=act,
                                      layer_norm=layer_norm, dropout=dropout,
                                      aggr=aggr)
        self.head = nn.Linear(hidden, 2)
        self.glob = (MLP([hidden, hidden, 2], act=act, dropout=dropout)
                     if self.global_branch else None)
        if zero_init_head and not direct:
            nn.init.zeros_(self.head.weight)
            nn.init.zeros_(self.head.bias)
            if self.glob is not None:
                last = [m for m in self.glob.net if isinstance(m, nn.Linear)][-1]
                nn.init.zeros_(last.weight)
                nn.init.zeros_(last.bias)

    # ------------------------------------------------------------------ utils
    def n_parameters(self) -> int:
        return count_parameters(self)

    def _pool(self, h: torch.Tensor, batch: torch.Tensor, n_graphs: int) -> torch.Tensor:
        pooled = h.new_zeros((n_graphs, h.shape[1]))
        pooled.index_add_(0, batch, h)
        cnt = torch.bincount(batch, minlength=n_graphs).clamp_min(1)
        return pooled / cnt.to(h.dtype).unsqueeze(1)

    # ---------------------------------------------------------------- forward
    def forward(self, batch: dict) -> dict:
        x = batch["x"]
        edge_index = batch["edge_index"]
        h = self.node_enc(x)
        e = None
        if self.edge_enc is not None:
            e = self.edge_enc(batch["edge_attr"])
        h = self.mp(h, edge_index, e)
        out = self.head(h)                       # (N, 2)
        d = {"node_re": out[:, 0], "node_im": out[:, 1]}
        if self.glob is not None:
            g = self.glob(self._pool(h, batch["batch"], int(batch["n_graphs"])))
            d["glob_re"] = g[:, 0]
            d["glob_im"] = g[:, 1]
        else:
            d["glob_re"] = None
            d["glob_im"] = None
        return d
