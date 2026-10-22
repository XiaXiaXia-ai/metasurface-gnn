# -*- coding: utf-8 -*-
"""Small MLP building blocks shared by the encoders, the message passing and the heads."""
from typing import Iterable, Optional, Sequence

import torch
import torch.nn as nn

ACTS = {"relu": nn.ReLU, "gelu": nn.GELU, "silu": nn.SiLU, "tanh": nn.Tanh}


def make_act(name: str) -> nn.Module:
    if name not in ACTS:
        raise ValueError("unknown activation %r (have %s)" % (name, sorted(ACTS)))
    return ACTS[name]()


class MLP(nn.Module):
    """dims[0] -> dims[1] -> ... -> dims[-1]; act+dropout after each hidden layer."""

    def __init__(self, dims: Sequence[int], act: str = "gelu", layer_norm: bool = False,
                 dropout: float = 0.0, last_act: bool = False):
        super().__init__()
        if len(dims) < 2:
            raise ValueError("MLP needs at least two dims")
        blocks = []
        for i in range(len(dims) - 1):
            blocks.append(nn.Linear(dims[i], dims[i + 1]))
            last = (i == len(dims) - 2)
            if not last or last_act:
                if layer_norm:
                    blocks.append(nn.LayerNorm(dims[i + 1]))
                blocks.append(make_act(act))
                if dropout > 0:
                    blocks.append(nn.Dropout(dropout))
        self.net = nn.Sequential(*blocks)
        self.out_dim = dims[-1]

    def forward(self, x):
        return self.net(x)


class NodeEncoder(nn.Module):
    """[x] -> hidden (one linear + activation by default, configurable depth)."""

    def __init__(self, in_dim: int, hidden: int, act: str = "gelu",
                 layers: int = 2, layer_norm: bool = False, dropout: float = 0.0):
        super().__init__()
        dims = [in_dim] + [hidden] * max(layers, 1)
        self.net = MLP(dims, act=act, layer_norm=layer_norm, dropout=dropout)

    def forward(self, x):
        return self.net(x)


class EdgeEncoder(nn.Module):
    def __init__(self, in_dim: int, hidden: int, act: str = "gelu",
                 layers: int = 2, layer_norm: bool = False, dropout: float = 0.0):
        super().__init__()
        if in_dim <= 0:
            raise ValueError("edge encoder needs in_dim > 0")
        dims = [in_dim] + [hidden] * max(layers, 1)
        self.net = MLP(dims, act=act, layer_norm=layer_norm, dropout=dropout)

    def forward(self, e):
        return self.net(e)


def count_parameters(module: nn.Module, trainable_only: bool = True) -> int:
    n = 0
    for p in module.parameters():
        if trainable_only and not p.requires_grad:
            continue
        n += p.numel()
    return int(n)


def describe_parameters(module: nn.Module) -> dict:
    out = {}
    for name, child in module.named_children():
        out[name] = count_parameters(child)
    out["__total__"] = count_parameters(module)
    return out
