# -*- coding: utf-8 -*-
"""Dataset index: CST far-field exports + per-case metadata -> Case objects.

On-disk contract (D:/dataset, produced by cst/dataset_gen.py)
------------------------------------------------------------
results/ff/ff_XXXX.txt   theta phi |E_theta|_dBsm |E_phi|_dBsm
                         2 deg grid, theta 0..90 (46), phi 0..358 (180) -> 8280
                         rows, theta-major (theta outer, phi inner).  AMPLITUDE
                         ONLY: the two dBsm columns are 20 log10 |E| with
                         sigma = |E_theta|^2 + |E_phi|^2 in m^2.
results/res_XXXX.json    index, seed, block, code (100 chars, 10x10 macro bits,
                         row-major, one bit covers a block x block cell patch),
                         freq_ghz, ff_step, specular_dbsm, mean_far_dbsm,
                         max_dbsm, timings.
codes/code_XXXX.txt      the same code in plain text (first line is a comment).

results/ff_er265_r2_b2/ff_10.txt (D:/ff_er265_r2_b2) 1 deg grid, 6 columns
                         theta phi |Eth| dB  arg Eth  |Eph| dB  arg Eph -- the
                         only complex-labelled sample we have (same design as
                         case 0000), used by the 'complex' loss mode.

Freezing the file list
----------------------
The CST queue is still producing cases, so the set of usable samples changes
while we work.  Every run therefore goes through a *snapshot* (a sha256 manifest)
written on first use and reused afterwards.  A sample is only usable when its
res_*.json exists -- the generator writes the far field first and the json last
(atomically), so the json is the completion marker.

Splits are grouped by layout_id.  In the current dataset every case has its own
i.i.d. random code, so layout_id is derived from the code itself: two cases with
the same code land in the same group, which is exactly the v2 'family' semantics
(res_*.json may also carry an explicit layout_id, which is preferred).
"""
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..config import DataCfg


# ---------------------------------------------------------------------- grid
@dataclass
class Grid:
    """Flattened (theta, phi) grid, theta-major as CST writes it."""

    theta: np.ndarray
    phi: np.ndarray
    n_theta: int = field(init=False)
    n_phi: int = field(init=False)

    def __post_init__(self):
        self.theta = np.asarray(self.theta, dtype=float).ravel()
        self.phi = np.asarray(self.phi, dtype=float).ravel()
        if self.theta.size != self.phi.size:
            raise ValueError("theta and phi must have the same length")
        self.n_theta = int(np.unique(np.round(self.theta, 6)).size)
        self.n_phi = int(np.unique(np.round(self.phi, 6)).size)
        if self.n_theta * self.n_phi != self.theta.size:
            raise ValueError("grid is not a complete theta x phi product")

    # ------------------------------------------------------------------ ctors
    @classmethod
    def from_step(cls, step: float = 2.0, theta_max: float = 90.0) -> "Grid":
        th = np.arange(0.0, theta_max + 1e-9, step)
        ph = np.arange(0.0, 360.0 - 1e-9, step)
        T, P = np.meshgrid(th, ph, indexing="ij")
        return cls(T.ravel(), P.ravel())

    @classmethod
    def from_files(cls, paths: Sequence[str]) -> "Grid":
        d = np.loadtxt(paths[0])
        return cls(d[:, 0], d[:, 1])

    # ------------------------------------------------------------------ props
    @property
    def size(self) -> int:
        return self.theta.size

    @property
    def shape(self) -> Tuple[int, int]:
        return (self.n_theta, self.n_phi)

    @property
    def theta_ax(self) -> np.ndarray:
        return np.unique(np.round(self.theta, 6))

    @property
    def phi_ax(self) -> np.ndarray:
        return np.unique(np.round(self.phi, 6))

    def to_grid(self, vals) -> np.ndarray:
        v = np.asarray(vals)
        if v.shape[-1] != self.size:
            raise ValueError("last axis %d != grid size %d" % (v.shape[-1], self.size))
        return v.reshape(v.shape[:-1] + self.shape)

    def band(self, lo: float, hi: float, right: bool = True) -> np.ndarray:
        m = (self.theta >= lo)
        m &= (self.theta <= hi) if right else (self.theta < hi)
        return m

    def __len__(self):
        return self.size


# ---------------------------------------------------------------------- case
@dataclass
class Case:
    idx: int
    name: str
    code10: np.ndarray                 # (n_bit, n_bit) macro bits
    bits: np.ndarray                   # (n_side, n_side) physical bits
    layout_id: str
    specular: float
    mean_far: float
    max_db: float
    seed: int
    block: int
    n_side: int
    freq_ghz: float
    ff_path: str
    res_path: str
    family: str = "random"

    @property
    def n_nodes(self) -> int:
        return int(self.bits.size)

    @property
    def code(self) -> str:
        return "".join(str(int(b)) for b in self.code10.ravel())

    @property
    def ones(self) -> int:
        return int(self.bits.sum())


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _sha256_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _read_code_file(path: str) -> Optional[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [ln.strip() for ln in fh]
    rows = [ln for ln in lines if ln and not ln.startswith("#") and set(ln) <= {"0", "1"}]
    if not rows:
        return None
    return "".join(rows)


def case_from_files(ff_path: str, res_path: str, grid: Grid,
                    block: int = 2, n_side: int = 20) -> Case:
    with open(res_path, "r", encoding="utf-8") as fh:
        rec = json.load(fh)
    code = rec.get("code")
    ns = int(rec.get("n_side", n_side))
    blk = int(rec.get("block", block))
    if code is None:
        raise ValueError("%s: no code field" % res_path)
    nbit = int(round(np.sqrt(len(code))))
    if nbit * nbit != len(code):
        raise ValueError("%s: code length %d is not a square" % (res_path, len(code)))
    code10 = np.array([int(c) for c in code], dtype=np.int8).reshape(nbit, nbit)
    if nbit * blk == ns:
        bits = np.repeat(np.repeat(code10, blk, axis=0), blk, axis=1)
    elif nbit == ns:
        bits = code10.copy()
        blk = 1
    else:
        raise ValueError("%s: code %dx%d does not match n_side %d (block %d)"
                         % (res_path, nbit, nbit, ns, blk))
    layout = rec.get("layout_id") or "L" + _sha1(code)[:12]
    idx = int(rec.get("index", os.path.basename(ff_path).split("_")[-1].split(".")[0]))
    return Case(idx=idx, name=os.path.basename(ff_path), code10=code10, bits=bits,
                layout_id=str(layout),
                specular=float(rec.get("specular_dbsm", np.nan)),
                mean_far=float(rec.get("mean_far_dbsm", np.nan)),
                max_db=float(rec.get("max_dbsm", np.nan)),
                seed=int(rec.get("seed", 0)), block=int(blk), n_side=ns,
                freq_ghz=float(rec.get("freq_ghz", 10.0)),
                ff_path=ff_path, res_path=res_path,
                family=str(rec.get("family", "random")))


def _ff_is_valid(path: str, grid: Grid, n_rows: Optional[int] = None) -> Tuple[bool, str]:
    try:
        d = np.loadtxt(path)
    except Exception as exc:                                  # noqa: BLE001
        return False, "unreadable: %s" % exc
    if d.ndim != 2 or d.shape[1] != 4:
        # exactly four columns (theta phi |Eth| |Eph|); accepting ">= 4" would
        # silently read the phase column of a 6-column complex export as |Ephi|.
        return False, "shape %s (expected 4 amplitude columns)" % (d.shape,)
    if d.shape[0] != grid.size:
        return False, "rows %d != %d" % (d.shape[0], grid.size)
    if not np.allclose(d[:, 0], grid.theta) or not np.allclose(d[:, 1], grid.phi):
        return False, "angle grid differs"
    return True, ""


def scan_cases(cfg: DataCfg, grid: Optional[Grid] = None,
               snapshot: Optional[dict] = None, verbose: bool = True,
               block: int = 2, n_side: int = 20,
               max_samples: Optional[int] = None
               ) -> Tuple[List[Case], List[str]]:
    """Enumerate usable cases; returns (cases, warnings)."""
    if grid is None:
        grid = Grid.from_step(2.0)
    ff_dir = os.path.join(cfg.root, cfg.ff_subdir)
    res_dir = os.path.join(cfg.root, cfg.res_subdir)
    if not os.path.isdir(ff_dir):
        raise FileNotFoundError("far-field directory not found: %s" % ff_dir)
    names = sorted(f for f in os.listdir(ff_dir) if f.startswith("ff_") and f.endswith(".txt"))
    if snapshot is not None:
        keep = {e["name"] for e in snapshot["files"]}
        missing = keep - set(names)
        if missing:
            raise FileNotFoundError("%d snapshot file(s) disappeared, e.g. %s"
                                    % (len(missing), sorted(missing)[:3]))
        names = [n for n in names if n in keep]
    cases, warns = [], []
    for name in names:
        res_path = os.path.join(res_dir, "res_" + name[3:-4] + ".json")
        if not os.path.isfile(res_path):
            continue                      # still being generated -> not usable
        ff_path = os.path.join(ff_dir, name)
        ok, why = _ff_is_valid(ff_path, grid)
        if not ok:
            warns.append("%s: %s" % (name, why))
            continue
        try:
            cases.append(case_from_files(ff_path, res_path, grid,
                                         block=block, n_side=n_side))
        except Exception as exc:                             # noqa: BLE001
            warns.append("%s: %s" % (name, exc))
    if snapshot is not None:
        by_name = {e["name"]: e for e in snapshot["files"]}
        for c in cases:
            e = by_name[c.name]
            if int(e["size"]) != os.path.getsize(c.ff_path):
                raise RuntimeError("%s changed size since the snapshot (%d != %d)"
                                   % (c.name, os.path.getsize(c.ff_path), e["size"]))
            want = e.get("sha256")
            if want:
                # size alone cannot detect an in-place rewrite of equal length;
                # verify the recorded digest when the snapshot carries one.
                got = _sha256_file(c.ff_path)
                if got != want:
                    raise RuntimeError("%s changed content since the snapshot "
                                       "(sha256 mismatch)" % c.name)
    cases.sort(key=lambda c: c.idx)
    if max_samples is not None and int(max_samples) > 0:
        # Z2: the cap belongs to the CALLER, not to the enumeration.  Applying it
        # here would also truncate build_snapshot(), which re-uses scan_cases.
        cases = cases[:int(max_samples)]
    if verbose and warns:
        print("[dataset] %d file(s) skipped: %s" % (len(warns), warns[:3]))
    return cases, warns


# ------------------------------------------------------------------ snapshot
def build_snapshot(cfg: DataCfg, grid: Optional[Grid] = None,
                   hash_files: bool = True, block: int = 2,
                   n_side: int = 20) -> dict:
    if grid is None:
        grid = Grid.from_step(2.0)
    cases, warns = scan_cases(cfg, grid, None, verbose=False, block=block,
                              n_side=n_side)
    files = []
    for c in cases:
        st = os.stat(c.ff_path)
        files.append({"name": c.name, "idx": c.idx, "size": st.st_size,
                      "mtime": st.st_mtime,
                      "sha256": _sha256_file(c.ff_path) if hash_files else None})
    return {"created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "root": cfg.root, "ff_subdir": cfg.ff_subdir,
            "grid": {"n_theta": grid.n_theta, "n_phi": grid.n_phi,
                     "step": float(grid.theta_ax[1] - grid.theta_ax[0])},
            "n": len(files), "files": files, "skipped": warns}


def save_snapshot(snapshot: dict, path: str) -> str:
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=1)
    return path


def load_snapshot(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------- targets
def load_target(case: Case, grid: Grid) -> dict:
    """Far-field export -> (sigma_db, |E_theta|, |E_phi|) on the grid."""
    d = np.loadtxt(case.ff_path)
    if d.shape[0] != grid.size:
        raise ValueError("%s: %d rows, grid has %d" % (case.ff_path, d.shape[0], grid.size))
    eth = 10.0 ** (d[:, 2] / 20.0)
    eph = 10.0 ** (d[:, 3] / 20.0)
    sig = eth ** 2 + eph ** 2
    return {"sig_db": 10.0 * np.log10(np.maximum(sig, 1e-300)),
            "eth_mag": eth, "eph_mag": eph, "sigma": sig}


def load_complex_case(path: str, front_only: bool = True) -> dict:
    """6-column export (theta phi |Eth|dB angEth |Eph|dB angEph) -> complex fields."""
    d = np.loadtxt(path)
    if d.shape[1] < 6:
        raise ValueError("%s: expected 6 columns, got %d" % (path, d.shape[1]))
    if front_only:
        d = d[d[:, 0] <= 90.0]
    eth = 10.0 ** (d[:, 2] / 20.0) * np.exp(1j * np.radians(d[:, 3]))
    eph = 10.0 ** (d[:, 4] / 20.0) * np.exp(1j * np.radians(d[:, 5]))
    return {"theta": d[:, 0], "phi": d[:, 1], "eth": eth, "eph": eph}


# -------------------------------------------------------------------- splits
def make_splits(cases: Sequence[Case], val_frac: float = 0.15,
                test_frac: float = 0.15, seed: int = 0) -> dict:
    """Group-aware 70/15/15 split by layout_id (no layout ever spans two splits)."""
    groups: Dict[str, List[int]] = {}
    for c in cases:
        groups.setdefault(c.layout_id, []).append(int(c.idx))
    names = sorted(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(names)
    n = len(cases)
    n_val = int(round(val_frac * n))
    n_test = int(round(test_frac * n))
    out = {"train": [], "val": [], "test": []}
    sizes = {"val": 0, "test": 0}
    turn = 0
    for g in names:
        gs = len(groups[g])
        if sizes["val"] < n_val and (turn % 2 == 0 or sizes["test"] >= n_test):
            out["val"].extend(groups[g])
            sizes["val"] += gs
        elif sizes["test"] < n_test:
            out["test"].extend(groups[g])
            sizes["test"] += gs
        else:
            out["train"].extend(groups[g])
        turn += 1
    for k in out:
        out[k] = sorted(out[k])
    # integrity checks
    seen: Dict[int, str] = {}
    for k, idxs in out.items():
        for i in idxs:
            if i in seen:
                raise RuntimeError("case %d appears in %s and %s" % (i, seen[i], k))
            seen[i] = k
    if len(seen) != n:
        raise RuntimeError("split covers %d of %d cases" % (len(seen), n))
    for g, idxs in groups.items():
        splits = {seen[i] for i in idxs}
        if len(splits) > 1:
            raise RuntimeError("layout %s spans %s" % (g, splits))
    return {"seed": int(seed), "val_frac": float(val_frac), "test_frac": float(test_frac),
            "n_cases": n, "n_groups": len(groups), "groups": groups,
            "cases": {str(c.idx): {"name": c.name, "layout_id": c.layout_id,
                                   "code": c.code, "split": seen[int(c.idx)]}
                      for c in cases},
            **out}


def save_splits(splits: dict, path: str) -> str:
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(splits, fh, indent=1)
    return path


def load_splits(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_or_make_splits(cfg: DataCfg, cases: Sequence[Case]) -> dict:
    if cfg.splits and os.path.isfile(cfg.splits):
        sp = load_splits(cfg.splits)
        have = {int(c.idx) for c in cases}
        for k in ("train", "val", "test"):
            sp[k] = [i for i in sp[k] if i in have]
        return sp
    return make_splits(cases, cfg.val_frac, cfg.test_frac, cfg.split_seed)


def split_indices(splits: dict, name: str) -> List[int]:
    if name not in ("train", "val", "test"):
        raise ValueError("split must be train/val/test")
    return [int(i) for i in splits[name]]
