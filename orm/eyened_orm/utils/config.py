import importlib
import os
from pathlib import Path


def lazy_import(fname):
    spec = importlib.util.spec_from_file_location("config", fname)
    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def get_config(env="dev"):
    fname = f"config.{env}.py"

    dir_path = Path(__file__).parent.parent

    fpath = dir_path / fname
    if not fpath.exists():
        raise FileNotFoundError(
            f"File {fname} does not exist. Did you forget to create it?"
        )
    config = lazy_import(fpath)
    return config.config