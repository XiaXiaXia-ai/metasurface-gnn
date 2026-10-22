# -*- coding: utf-8 -*-
"""Configuration schema: dataclasses + a YAML loader that validates.

Every field has a default, so a YAML file only needs the values it overrides.
Unknown keys are a hard error (typos in a config are otherwise silent), as are
out-of-range values.  Config.to_dict() round-trips to YAML for archiving the
exact configuration used by a training run.

Path handling: values that look like paths are expanded (~, environment
variables) and, if relative, resolved against the current working directory.
Relative paths inside a YAML are therefore resolved from wherever you launch the
scripts, which is what the documented commands assume.
"""
import dataclasses
import os
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, List, Optional, Tuple, Union, get_args, get_origin

import yaml


class ConfigError(ValueError):
    """Raised for an invalid or unknown configuration entry."""


# --------------------------------------------------------------------- sections
@dataclass
class DataCfg:
    root: str = "D:/dataset"
    ff_subdir: str = "results/ff"
    res_subdir: str = "results"
    codes_subdir: str = "codes"
    snapshot: Optional[str] = None      # frozen file manifest (None -> build one)
    splits: Optional[str] = None        # splits.json (None -> derive from split_*)
    split_seed: int = 20261022
    val_frac: float = 0.15
    test_frac: float = 0.15
    max_samples: int = 0                # 0 = every sample in the snapshot
    complex_ff: Optional[str] = "D:/ff_er265_r2_b2/ff_10.txt"
    cache: bool = True                  # keep decoded samples in RAM


@dataclass
class GraphCfg:
    radius: int = 1                     # Chebyshev neighbourhood radius (1 -> 8 nbrs)
    self_loops: bool = False
    edge_features: bool = True


@dataclass
class PhysicsCfg:
    freq_ghz: float = 10.0
    n_side: int = 20                    # physical cells per side
    block: int = 2                      # one code bit covers block x block cells
    period_mm: float = 14.0
    projection: str = "vector"          # "vector" | "scalar"
    gamma_source: str = "floquet"       # "floquet" | "unit"  (theory/REPORT.md 5.2)
    unit_table: Optional[str] = None    # csv for the angle-dependent extension
    patch_r_mm: Tuple[float, float] = (4.7, 2.0)


@dataclass
class ModelCfg:
    name: str = "m3"                    # m0 | m1 | m2 | m3
    hidden: int = 64
    n_layers: int = 3
    global_branch: bool = True          # M3: per-sample complex common mode b
    dropout: float = 0.0
    act: str = "gelu"
    layer_norm: bool = True
    base_width: int = 16                # M1 U-Net width
    out_rank: int = 4                   # M1 factorised read-out rank
    zero_init_head: bool = True


@dataclass
class LossCfg:
    mode: str = "power"                 # power (amplitude-only labels) | complex
    compression: str = "asinh"          # none | asinh
    compression_db: float = 3.0         # scale of the asinh knee, in dB
    angle_weight: str = "solid_angle"   # uniform | solid_angle
    weight_floor: float = 0.2           # additive floor so theta=0 is not weighted 0
    mainlobe_deg: float = 6.0
    mainlobe_boost: float = 1.0         # extra weight inside mainlobe_deg
    null_weight: float = 0.0            # extra term on the deep (null) region
    null_depth_db: float = 25.0
    eps_rel: float = 1.0e-3             # regulariser of the relative complex loss
    complex_compress: bool = True       # per-angle relative normalisation


@dataclass
class OptimCfg:
    lr: float = 1.0e-3
    weight_decay: float = 1.0e-4
    batch_size: int = 8
    epochs: int = 60
    patience: int = 15
    grad_clip: float = 1.0
    scheduler: str = "cosine"           # none | cosine
    min_lr: float = 1.0e-5


@dataclass
class RuntimeCfg:
    threads: int = 4
    dtype: str = "float32"              # float32 | float64
    device: str = "cpu"
    log_every: int = 1


@dataclass
class EvalCfg:
    db_floor: float = -60.0
    meas_floor_db: float = -30.0        # samples below this are excluded from rho/bias
    rho_band: Tuple[float, float] = (6.0, 90.0)
    bands: Tuple[Tuple[float, float], ...] = (
        (0.0, 5.0), (5.0, 15.0), (15.0, 30.0), (30.0, 60.0), (60.0, 90.0))


@dataclass
class Config:
    seed: int = 0
    seeds: Tuple[int, ...] = (0, 1, 2)
    out_dir: str = "runs"
    data: DataCfg = field(default_factory=DataCfg)
    graph: GraphCfg = field(default_factory=GraphCfg)
    physics: PhysicsCfg = field(default_factory=PhysicsCfg)
    model: ModelCfg = field(default_factory=ModelCfg)
    loss: LossCfg = field(default_factory=LossCfg)
    optim: OptimCfg = field(default_factory=OptimCfg)
    runtime: RuntimeCfg = field(default_factory=RuntimeCfg)
    eval: EvalCfg = field(default_factory=EvalCfg)
    path: Optional[str] = None          # source YAML (not written back)

    # ---------------------------------------------------------------- helpers
    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d.pop("path", None)
        return d

    def save(self, path: str) -> str:
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(_plain(self.to_dict()), fh, sort_keys=False,
                           allow_unicode=True)
        return path

    def validate(self) -> "Config":
        _validate(self)
        return self


# ---------------------------------------------------------------- construction
def _is_optional(tp) -> bool:
    return get_origin(tp) is Union and type(None) in get_args(tp)


def _strip_optional(tp):
    if _is_optional(tp):
        args = [a for a in get_args(tp) if a is not type(None)]
        return args[0] if args else Any
    return tp


def _check_scalar(val, tp, path):
    tp = _strip_optional(tp)
    if tp is Any:
        return val
    if tp is bool:
        if not isinstance(val, bool):
            raise ConfigError("%s: expected bool, got %r" % (path, val))
        return val
    if tp is int:
        if isinstance(val, bool) or not isinstance(val, int):
            raise ConfigError("%s: expected int, got %r" % (path, val))
        return val
    if tp is float:
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ConfigError("%s: expected float, got %r" % (path, val))
        return float(val)
    if tp is str:
        if not isinstance(val, str):
            raise ConfigError("%s: expected str, got %r" % (path, val))
        return val
    return val


def _check_container(val, tp, path):
    tp = _strip_optional(tp)
    origin = get_origin(tp)
    args = get_args(tp)
    if origin in (tuple, Tuple):
        if not isinstance(val, (list, tuple)):
            raise ConfigError("%s: expected a sequence, got %r" % (path, val))
        if len(args) == 2 and args[1] is Ellipsis:          # Tuple[int, ...]
            return tuple(_check_scalar(v, args[0], "%s[%d]" % (path, i))
                         for i, v in enumerate(val))
        if args and len(val) != len(args):
            raise ConfigError("%s: expected %d entries, got %d"
                              % (path, len(args), len(val)))
        out = []
        for i, v in enumerate(val):
            sub = args[i] if i < len(args) else Any
            if get_origin(sub) in (tuple, Tuple):
                out.append(_check_container(v, sub, "%s[%d]" % (path, i)))
            else:
                out.append(_check_scalar(v, sub, "%s[%d]" % (path, i)))
        return tuple(out)
    if origin in (list, List):
        if not isinstance(val, (list, tuple)):
            raise ConfigError("%s: expected a sequence, got %r" % (path, val))
        return [_check_scalar(v, args[0] if args else Any, "%s[%d]" % (path, i))
                for i, v in enumerate(val)]
    return val


def _construct(cls, raw, path):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("%s: expected a mapping, got %r" % (path, type(raw).__name__))
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ConfigError("%s: unknown key(s) %s (known: %s)"
                          % (path, unknown, sorted(known)))
    kw = {}
    for f in fields(cls):
        if f.name not in raw:
            continue
        val = raw[f.name]
        sub_path = "%s.%s" % (path, f.name)
        tp = _strip_optional(f.type)
        if val is None:
            if not _is_optional(f.type):
                raise ConfigError("%s: null is not allowed" % sub_path)
            kw[f.name] = None
        elif is_dataclass(tp):
            kw[f.name] = _construct(tp, val, sub_path)
        else:
            kw[f.name] = _check_container(val, f.type, sub_path)
    return cls(**kw)


def _plain(obj):
    """Recursively convert tuples/dataclasses into YAML-friendly python objects."""
    if is_dataclass(obj):
        return {f.name: _plain(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


# ------------------------------------------------------------------ validation
def _validate(c: Config) -> None:
    p = c.physics
    if p.freq_ghz <= 0:
        raise ConfigError("physics.freq_ghz must be > 0")
    if p.n_side < 2:
        raise ConfigError("physics.n_side must be >= 2")
    if p.block < 1 or p.n_side % p.block:
        raise ConfigError("physics.block must divide physics.n_side")
    if p.period_mm <= 0:
        raise ConfigError("physics.period_mm must be > 0")
    if p.projection not in ("vector", "scalar"):
        raise ConfigError("physics.projection must be 'vector' or 'scalar'")
    if p.gamma_source not in ("floquet", "unit"):
        raise ConfigError("physics.gamma_source must be 'floquet' or 'unit'")
    if c.graph.radius < 1:
        raise ConfigError("graph.radius must be >= 1")
    m = c.model
    if m.name not in ("m0", "m1", "m2", "m3"):
        raise ConfigError("model.name must be one of m0/m1/m2/m3")
    if m.hidden < 4:
        raise ConfigError("model.hidden must be >= 4")
    if m.n_layers < 1:
        raise ConfigError("model.n_layers must be >= 1")
    if m.act not in ("relu", "gelu", "silu", "tanh"):
        raise ConfigError("model.act must be relu/gelu/silu/tanh")
    lo = c.loss
    if lo.mode not in ("power", "complex"):
        raise ConfigError("loss.mode must be 'power' or 'complex'")
    if lo.compression not in ("none", "asinh"):
        raise ConfigError("loss.compression must be 'none' or 'asinh'")
    if lo.compression_db <= 0:
        raise ConfigError("loss.compression_db must be > 0")
    if lo.angle_weight not in ("uniform", "solid_angle"):
        raise ConfigError("loss.angle_weight must be 'uniform' or 'solid_angle'")
    if not (0.0 <= lo.weight_floor <= 1.0):
        raise ConfigError("loss.weight_floor must be in [0, 1]")
    if lo.mainlobe_boost < 0:
        raise ConfigError("loss.mainlobe_boost must be >= 0")
    o = c.optim
    if o.lr <= 0:
        raise ConfigError("optim.lr must be > 0")
    if o.batch_size < 1:
        raise ConfigError("optim.batch_size must be >= 1")
    if o.epochs < 1:
        raise ConfigError("optim.epochs must be >= 1")
    if o.patience < 1:
        raise ConfigError("optim.patience must be >= 1")
    if o.scheduler not in ("none", "cosine"):
        raise ConfigError("optim.scheduler must be 'none' or 'cosine'")
    d = c.data
    if not (0.0 <= d.val_frac < 1.0) or not (0.0 <= d.test_frac < 1.0):
        raise ConfigError("data.val_frac / test_frac must be in [0, 1)")
    if d.val_frac + d.test_frac >= 1.0:
        raise ConfigError("data.val_frac + data.test_frac must be < 1")
    if d.max_samples < 0:
        raise ConfigError("data.max_samples must be >= 0")
    r = c.runtime
    if r.dtype not in ("float32", "float64"):
        raise ConfigError("runtime.dtype must be 'float32' or 'float64'")
    if r.threads < 1:
        raise ConfigError("runtime.threads must be >= 1")
    e = c.eval
    if e.rho_band[0] >= e.rho_band[1]:
        raise ConfigError("eval.rho_band must be increasing")
    for b in e.bands:
        if b[0] >= b[1]:
            raise ConfigError("eval.bands entries must be increasing")


def _expand(value: str) -> str:
    return os.path.expanduser(os.path.expandvars(value))


def load_config(path: Optional[str] = None, overrides: Optional[dict] = None) -> Config:
    """Load (and validate) a YAML config; overrides is a nested dict merged in."""
    raw: dict = {}
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict):
            raise ConfigError("%s: top level must be a mapping" % path)
    if overrides:
        raw = _deep_merge(raw, overrides)
    cfg = _construct(Config, raw, "config")
    cfg.path = os.path.abspath(path) if path else None
    cfg.out_dir = _expand(cfg.out_dir)
    cfg.data.root = _expand(cfg.data.root)
    for name in ("snapshot", "splits", "complex_ff"):
        v = getattr(cfg.data, name)
        if v:
            setattr(cfg.data, name, _expand(v))
    if cfg.physics.unit_table:
        cfg.physics.unit_table = _expand(cfg.physics.unit_table)
    return cfg.validate()


def _deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def config_from_dict(d: dict) -> Config:
    return _construct(Config, d, "config").validate()
