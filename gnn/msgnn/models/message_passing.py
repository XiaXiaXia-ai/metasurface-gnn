# -*- coding: utf-8 -*-
"""Edge-conditioned message passing, written out by hand (no DGL / PyG).

One block:
    m_ij  = MLP_msg([h_i, h_j, e_ij])            (i = source, j = target)
    agg_j = sum_i m_ij                          (mean optional)
    h_j   = LayerNorm( h_j + dropout(act(MLP_upd([h_j, agg_j]))) )

The aggregation is a scatter-add on the target index, so a batch of disjoint
graphs (concatenated, edge_index already offset) costs one pass and graphs never
mix: edges only ever point inside their own graph.
"""
from typing import Optional

import torch
import torch.nn as nn

from .encoders import MLP, make_act


class MessagePassingLayer(nn.Module):
    def __init__(self, hidden: int, edge_dim: int, act: str = "gelu",
                 layer_norm: bool = True, dropout: float = 0.0, aggr: str = "sum"):
        super().__init__()
        if aggr not in ("sum", "mean"):
            raise ValueError("aggr must be 'sum' or 'mean'")
        self.aggr = aggr
        self.act = make_act(act)
        self.drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()
        msg_in = 2 * hidden + max(edge_dim, 0)
        self.msg = MLP([msg_in, hidden, hidden], act=act, dropout=dropout)
        self.upd = MLP([2 * hidden, hidden, hidden], act=act, dropout=dropout)
        self.norm = nn.LayerNorm(hidden) if layer_norm else None

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor,
                edge_attr: Optional[torch.Tensor] = None) -> torch.Tensor:
        src, dst = edge_index[0], edge_index[1]
        parts = [h[src], h[dst]]
        if edge_attr is not None and edge_attr.dim() == 2 and edge_attr.shape[1] > 0:
            parts.append(edge_attr)
        m = self.msg(torch.cat(parts, dim=-1))
        agg = h.new_zeros(h.shape)
        agg.index_add_(0, dst, m)
        if self.aggr == "mean":
            deg = torch.bincount(dst, minlength=h.shape[0]).clamp_min(1)
            agg = agg / deg.to(h.dtype).unsqueeze(1)
        out = self.upd(torch.cat([h, agg], dim=-1))
        h = h + self.drop(self.act(out))
        if self.norm is not None:
            h = self.norm(h)
        return h


class MessagePassingStack(nn.Module):
    def __init__(self, n_layers: int, hidden: int, edge_dim: int, act: str = "gelu",
                 layer_norm: bool = True, dropout: float = 0.0, aggr: str = "sum"):
        super().__init__()
        self.layers = nn.ModuleList([
            MessagePassingLayer(hidden, edge_dim, act, layer_norm, dropout, aggr)
            for _ in range(n_layers)])

    def forward(self, h, edge_index, edge_attr=None):
        for layer in self.layers:
            h = layer(h, edge_index, edge_attr)
        return h
