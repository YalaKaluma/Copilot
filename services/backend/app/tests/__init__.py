"""Test suite for FastAPI backend."""

import sys
from pathlib import Path

# Make repo-level shared modules (e.g., `packages`) importable when tests run
# from `services/backend/app` in CI/local and Docker environments.
_current = Path(__file__).resolve().parent
for _parent in [_current, *_current.parents]:
    if (_parent / "packages").is_dir():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break
