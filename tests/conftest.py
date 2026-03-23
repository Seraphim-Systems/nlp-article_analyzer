"""Test bootstrap: ensure src/ is importable when pytest runs from repo root."""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")

for p in (_REPO_ROOT, _SRC_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)
