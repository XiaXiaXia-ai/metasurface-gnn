"""msgnn -- physics-guided graph neural network for coding-metasurface
scattering prediction (20 x 20 1-bit reflectarray, 10 GHz).

Package layout
--------------
msgnn.config              dataclass config + YAML load/validate
msgnn.data.*              dataset / graph construction / normaliser
msgnn.physics.*           unit-cell library, differentiable vector far field,
                          local-periodic baseline (M0)
msgnn.models.*            M1 CNN, M2/M3 GNN, message passing, pipeline
msgnn.losses              power / complex loss with dynamic-range compression
msgnn.train/evaluate/predict
"""
import os as _os

# torch and numpy (MKL) both ship an OpenMP runtime; importing both aborts the
# interpreter with "OMP: Error #15" on this Anaconda install.  Setting the
# documented escape hatch here means every entry point that imports msgnn
# (scripts, tests, notebooks) just works.  Must happen before torch is imported,
# which is guaranteed because this file runs before any msgnn submodule.
_os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from .config import Config, ConfigError, load_config

__version__ = "0.1.0"
__all__ = ["Config", "ConfigError", "load_config", "__version__"]
