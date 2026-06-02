# -*- coding: utf-8 -*-
"""Resource paths that work from source and PyInstaller bundles."""

import sys
from pathlib import Path


def project_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return project_root().joinpath(*parts)
