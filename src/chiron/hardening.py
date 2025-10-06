"""Runtime hardening utilities used across the Chiron toolchain."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import random
import sys
from contextlib import suppress
from typing import Any

_MAX_SEED = (1 << 32) - 1


def normalise_seed(seed: Any) -> int:
    """Normalise *seed* into the range accepted by numpy/random generators."""

    if seed is None:
        return 0

    try:
        value = int(seed)
    except (TypeError, ValueError):
        return 0

    value %= _MAX_SEED + 1
    if value < 0:
        value += _MAX_SEED + 1
    return value


_HOOK_INSTALLED = False


class _ThincSeedGuardFinder(importlib.abc.MetaPathFinder):
    """Meta path finder that patches ``thinc.util`` on first import."""

    def __init__(self) -> None:
        self._active = False

    def install(self) -> None:
        if self._active:
            return
        sys.meta_path.insert(0, self)
        self._active = True

    def deactivate(self) -> None:
        global _HOOK_INSTALLED, _FINDER

        if not self._active:
            return

        self._active = False
        with suppress(ValueError):
            sys.meta_path.remove(self)

        _HOOK_INSTALLED = False
        if _FINDER is self:
            _FINDER = None

    def find_spec(
        self,
        fullname: str,
        path: Any,
        target: Any = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname != "thinc.util":
            return None

        spec = importlib.util.find_spec(fullname)
        if not spec or not spec.loader:
            return spec

        loader = spec.loader
        original_exec = getattr(loader, "exec_module", None)
        if original_exec is None:
            return spec

        def exec_module(module: Any) -> None:
            try:
                original_exec(module)
            except Exception:
                raise
            else:
                _apply_seed_guard(module)
            finally:
                with suppress(AttributeError, TypeError):
                    setattr(loader, "exec_module", original_exec)  # noqa: B010
                self.deactivate()

        setattr(loader, "exec_module", exec_module)  # noqa: B010
        return spec


_FINDER: _ThincSeedGuardFinder | None = None


def _apply_seed_guard(thinc_util: Any) -> bool:
    current = getattr(thinc_util, "fix_random_seed", None)
    if not callable(current) or getattr(current, "_chiron_seed_guard", False):
        return False

    def safe_fix_random_seed(seed: int = 0) -> None:
        normalised = normalise_seed(seed)
        try:
            current(normalised)
            return
        except ValueError:
            pass

        import numpy as np

        # local import to avoid mandatory dependency at module import time

        random.seed(normalised)
        np.random.seed(normalised)

        if getattr(thinc_util, "has_torch", False):  # pragma: no branch - optional
            thinc_util.torch.manual_seed(normalised)

        if getattr(thinc_util, "has_cupy_gpu", False):  # pragma: no branch - optional
            thinc_util.cupy.random.seed(normalised)
            if getattr(thinc_util, "has_torch", False) and getattr(
                thinc_util, "has_torch_cuda_gpu", False
            ):  # pragma: no branch - optional
                thinc_util.torch.cuda.manual_seed_all(normalised)
                thinc_util.torch.backends.cudnn.deterministic = True
                thinc_util.torch.backends.cudnn.benchmark = False

    safe_fix_random_seed._chiron_seed_guard = True  # type: ignore[attr-defined]
    safe_fix_random_seed.__wrapped__ = current  # type: ignore[attr-defined]

    setattr(thinc_util, "fix_random_seed", safe_fix_random_seed)  # noqa: B010
    return True


def install_thinc_seed_guard() -> bool:
    """Patch ``thinc.util.fix_random_seed`` to tolerate wide seed values."""

    global _HOOK_INSTALLED, _FINDER

    try:
        thinc_util = importlib.import_module("thinc.util")
    except Exception:  # pragma: no cover - optional dependency
        if _HOOK_INSTALLED:
            return False

        finder = _ThincSeedGuardFinder()
        finder.install()
        _HOOK_INSTALLED = True
        _FINDER = finder
        return False

    if _FINDER is not None:
        _FINDER.deactivate()

    return _apply_seed_guard(thinc_util)


__all__ = ["install_thinc_seed_guard", "normalise_seed", "_MAX_SEED"]
