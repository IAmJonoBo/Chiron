"""Tests for runtime hardening helpers."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import types

import pytest


class DummySeedRecorder:
    """Record seeds passed to the patched thinc util function."""

    def __init__(self) -> None:
        self.seeds: list[int] = []

    def __call__(self, seed: int = 0) -> None:
        self.seeds.append(seed)


@pytest.fixture()
def hardening_module(monkeypatch: pytest.MonkeyPatch):
    """Provide a reloaded ``chiron.hardening`` module for isolated tests."""

    # Install a stub ``thinc.util`` module before importing hardening.
    recorder = DummySeedRecorder()
    thinc_pkg = types.ModuleType("thinc")
    util_module = types.ModuleType("thinc.util")
    util_module.fix_random_seed = recorder  # type: ignore[attr-defined]
    util_module.has_torch = False  # required attributes referenced by guard
    util_module.has_cupy_gpu = False
    util_module.has_torch_cuda_gpu = False

    monkeypatch.setitem(sys.modules, "thinc", thinc_pkg)
    monkeypatch.setitem(sys.modules, "thinc.util", util_module)

    module = importlib.import_module("chiron.hardening")
    importlib.reload(module)

    yield module, recorder, util_module

    # Ensure subsequent imports see a clean module instance.
    sys.modules.pop("chiron.hardening", None)


class TestNormaliseSeed:
    """Tests for the ``normalise_seed`` helper."""

    def test_handles_negative_values(self, hardening_module) -> None:
        module, _, _ = hardening_module
        normalised = module.normalise_seed(-5)
        assert normalised >= 0
        assert normalised <= module._MAX_SEED

    def test_clamps_large_values(self, hardening_module) -> None:
        module, _, _ = hardening_module
        normalised = module.normalise_seed(2**40)
        assert normalised <= module._MAX_SEED

    def test_defaults_to_zero(self, hardening_module) -> None:
        module, _, _ = hardening_module
        assert module.normalise_seed(None) == 0


class TestInstallThincSeedGuard:
    """Tests for installing the thinc seeding guard."""

    def test_installs_wrapper_once(self, hardening_module) -> None:
        module, recorder, util_module = hardening_module

        assert module.install_thinc_seed_guard() is True
        assert module.install_thinc_seed_guard() is False

        # The wrapper should invoke the original recorder with a normalised seed.
        util_module.fix_random_seed(-1)
        assert recorder.seeds
        assert recorder.seeds[-1] >= 0
        assert recorder.seeds[-1] <= module._MAX_SEED

    def test_handles_import_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "thinc", None)
        import chiron.hardening as hardening

        assert hardening.install_thinc_seed_guard() is False

    def test_import_hook_cleans_up_after_lazy_import(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in ("thinc.util", "chiron.hardening"):
            sys.modules.pop(key, None)

        import chiron.hardening as hardening
        importlib.reload(hardening)

        thinc_pkg = types.ModuleType("thinc")
        thinc_pkg.__path__ = []  # mark as package for submodule imports
        monkeypatch.setitem(sys.modules, "thinc", thinc_pkg)

        original_import_module = importlib.import_module

        def fail_import(name: str, package: str | None = None):
            if name == "thinc.util":
                raise ModuleNotFoundError("stub")
            return original_import_module(name, package)

        monkeypatch.setattr(importlib, "import_module", fail_import)

        assert hardening.install_thinc_seed_guard() is False
        finder = hardening._FINDER
        assert finder is not None
        assert finder in sys.meta_path

        recorder = DummySeedRecorder()

        class DummyLoader(importlib.abc.Loader):
            def create_module(self, spec: importlib.machinery.ModuleSpec):
                return types.ModuleType(spec.name)

            def exec_module(self, module: types.ModuleType) -> None:
                module.fix_random_seed = recorder  # type: ignore[attr-defined]
                module.has_torch = False
                module.has_cupy_gpu = False
                module.has_torch_cuda_gpu = False

        spec = importlib.machinery.ModuleSpec("thinc.util", DummyLoader())
        original_find_spec = importlib.util.find_spec

        def fake_find_spec(name: str, path=None):
            if name == "thinc.util":
                return spec
            return original_find_spec(name, path)

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
        monkeypatch.setattr(importlib, "import_module", original_import_module)

        module = importlib.import_module("thinc.util")
        module.fix_random_seed(-5)

        assert recorder.seeds
        assert recorder.seeds[-1] >= 0
        assert finder not in sys.meta_path
        assert hardening._FINDER is None

        sys.modules.pop("thinc.util", None)

    def test_import_hook_restores_loader_exec_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in ("thinc.util", "chiron.hardening"):
            sys.modules.pop(key, None)

        import chiron.hardening as hardening
        importlib.reload(hardening)

        thinc_pkg = types.ModuleType("thinc")
        thinc_pkg.__path__ = []
        monkeypatch.setitem(sys.modules, "thinc", thinc_pkg)

        original_import_module = importlib.import_module

        def fail_import(name: str, package: str | None = None):
            if name == "thinc.util":
                raise ModuleNotFoundError("stub")
            return original_import_module(name, package)

        monkeypatch.setattr(importlib, "import_module", fail_import)

        assert hardening.install_thinc_seed_guard() is False
        finder = hardening._FINDER
        assert finder is not None

        recorder = DummySeedRecorder()

        class DummyLoader(importlib.abc.Loader):
            def __init__(self) -> None:
                self.exec_calls = 0

            def create_module(self, spec: importlib.machinery.ModuleSpec):
                return types.ModuleType(spec.name)

            def exec_module(self, module: types.ModuleType) -> None:
                self.exec_calls += 1
                module.fix_random_seed = recorder  # type: ignore[attr-defined]
                module.has_torch = False
                module.has_cupy_gpu = False
                module.has_torch_cuda_gpu = False

        loader = DummyLoader()
        original_exec = loader.exec_module
        spec = importlib.machinery.ModuleSpec("thinc.util", loader)

        original_find_spec = importlib.util.find_spec

        def fake_find_spec(name: str, path=None):
            if name == "thinc.util":
                return spec
            return original_find_spec(name, path)

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
        monkeypatch.setattr(importlib, "import_module", original_import_module)

        module = importlib.import_module("thinc.util")
        module.fix_random_seed(123)

        assert recorder.seeds
        assert loader.exec_calls == 1

        restored_exec = getattr(loader.exec_module, "__func__", loader.exec_module)
        original_callable = getattr(original_exec, "__func__", original_exec)
        assert restored_exec is original_callable

        assert finder not in sys.meta_path
        assert hardening._FINDER is None

        sys.modules.pop("thinc.util", None)
