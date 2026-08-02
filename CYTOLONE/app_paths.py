"""Resolve CYTOLONE's persistent paths without breaking the CLI layout.

The app launcher sets ``CYTOLONE_DATA_ROOT`` to a directory in the user's
Library. Development CLI launches leave it unset and therefore continue to use
the repository-relative paths used before the app bundle.
"""

import os
from pathlib import Path


DATA_ROOT_ENV = "CYTOLONE_DATA_ROOT"


def app_data_root():
    value = os.environ.get(DATA_ROOT_ENV)
    if not value:
        return None
    return Path(value).expanduser()


def config_path(default="CYTOLONE/config.ini"):
    root = app_data_root()
    return root / "config.ini" if root is not None else Path(default)


def models_path(default="mlx_models"):
    root = app_data_root()
    return root / "Models" if root is not None else Path(default)


def debug_path(default="debug_images"):
    root = app_data_root()
    return root / "Debug" if root is not None else Path(default)
