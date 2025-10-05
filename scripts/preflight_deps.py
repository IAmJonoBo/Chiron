#!/usr/bin/env python3
"""Wrapper entry point for dependency preflight validation.

This thin script exists so tooling such as Renovate can invoke the
preflight checks without depending on the package being installed in the
current interpreter. It simply delegates to :mod:`chiron.deps.preflight`
so all of the real logic lives beside the library code.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT / "src"))
    runpy.run_module("chiron.deps.preflight", run_name="__main__")
