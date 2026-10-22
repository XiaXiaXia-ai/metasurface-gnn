# -*- coding: utf-8 -*-
"""Model factory and the physics pipeline: graph -> q -> radiation -> sigma(dB).

Model map (aligned with the plan and with theory/REPORT.md)
    M0  q = q0                                        no parameters
    M1  CNN directly predicts sigma_dB on the grid    no physics, no graph
    M2  q = GNN(graph)                                physics, no baseline
    M3  q = q0 + dq + b                               physics + residual + global mode

All four are scored by the same loss and the same metrics, so 'M3 vs M0' answers
'the learned correction vs the local-periodic baseline' and 'M3 vs M2' answers
'the value of the baseline skip connection'.
"""
from typing import Optional

import numpy as np
import torch
import torch.nn as nn

from ..config import Config
from ..physics.radiation import FarFieldOperator
from .cnn_baseline import CNNBaseline
from .encoders import count_parameters
from .residual_gnn import GraphNet


class PhysicsPipeline(nn.Module):
    """Wraps a backbone and the (parameter-free) far-field operator."""

    def __init__(self, kind: str, net: Optional[nn.Module],
                 operator: Optional[FarFieldOperator] = None,
                 db_floor: float = -60.0):
        super().__init__()
        if kind not in ("m0", "m1", "m2", "m3"):
            raise ValueError("kind must be m0/m1/m2/m3")
        self.kind = kind
        self.net = net
        self.op = operator
        self.db_floor = float(db_floor)
        if kind != "m1" and operator is None:
            raise ValueError("the physics models need a FarFieldOperator")

    def q_of(self, batch: dict):
        """Return (q_re, q_im) per node for the physics models."""
        q0_re = batch.get("q0_re")
        q0_im = batch.get("q0_im")
        if self.kind == "m0":
            return q0_re, q0_im
        out = self.net(batch)
        n_re, n_im = out["node_re"], out["node_im"]
        if self.kind == "m2":
            return n_re, n_im
        # M3: residual + global common mode
        q_re = q0_re + n_re
        q_im = q0_im + n_im
        if out.get("glob_re") is not None:
            g = batch["batch"]
            q_re = q_re + out["glob_re"][g]
            q_im = q_im + out["glob_im"][g]
        return q_re, q_im

    def forward(self, batch: dict, return_fields: bool = False) -> dict:
        if self.kind == "m1":
            sig = self.net(batch)
            return {"sig_db": sig}
        q_re, q_im = self.q_of(batch)
        # q is a flat (B*N,) node tensor while FarFieldOperator.__call__ expects
        # (B, N): reshape when all graphs have the same size, otherwise evaluate
        # per graph and concatenate.
        n_graphs = int(batch.get("n_graphs", 1))
        ptr = batch.get("ptr")
        if n_graphs > 1 and ptr is not None:
            sizes = (ptr[1:] - ptr[:-1]).tolist()
            if len(set(sizes)) == 1:
                q_re = q_re.view(n_graphs, sizes[0])
                q_im = q_im.view(n_graphs, sizes[0])
            else:
                per = [self.op(q_re[int(ptr[i]):int(ptr[i + 1])],
                               q_im[int(ptr[i]):int(ptr[i + 1])])
                       for i in range(n_graphs)]
                fields = {k: torch.cat([p[k] for p in per], 0) for k in per[0]}
                d = {"sig_db": self.op.sigma_db(fields, self.db_floor)}
                if return_fields:
                    d.update(fields)
                    d["q_re"] = q_re
                    d["q_im"] = q_im
                return d
        fields = self.op(q_re, q_im)
        d = {"sig_db": self.op.sigma_db(fields, self.db_floor)}
        if return_fields:
            d.update(fields)
            d["q_re"] = q_re
            d["q_im"] = q_im
        return d

    def n_parameters(self) -> int:
        return count_parameters(self)


def build_net(cfg: Config, node_dim: int, edge_dim: int, n_theta: int,
              n_phi: int) -> Optional[nn.Module]:
    name = cfg.model.name
    if name == "m0":
        return None
    if name == "m1":
        pad = 2 ** int(np.ceil(np.log2(max(cfg.physics.n_side, 4))))
        return CNNBaseline(n_side=cfg.physics.n_side, n_theta=n_theta, n_phi=n_phi,
                           width=cfg.model.base_width, rank=cfg.model.out_rank,
                           act=cfg.model.act, dropout=cfg.model.dropout,
                           pad=pad)
    return GraphNet(node_dim=node_dim, edge_dim=edge_dim,
                    hidden=cfg.model.hidden, n_layers=cfg.model.n_layers,
                    act=cfg.model.act, layer_norm=cfg.model.layer_norm,
                    dropout=cfg.model.dropout,
                    global_branch=bool(cfg.model.global_branch and name == "m3"),
                    direct=(name == "m2"),
                    zero_init_head=cfg.model.zero_init_head)


def build_pipeline(cfg: Config, node_dim: int, edge_dim: int,
                   n_theta: int, n_phi: int,
                   operator: Optional[FarFieldOperator]) -> PhysicsPipeline:
    net = build_net(cfg, node_dim, edge_dim, n_theta, n_phi)
    return PhysicsPipeline(cfg.model.name, net, operator, cfg.eval.db_floor)
