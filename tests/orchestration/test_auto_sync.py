from __future__ import annotations

from typing import Any, cast

from chiron.orchestration.auto_sync import (
    AutoSyncConfig,
    AutoSyncOrchestrator,
)


class FakeCoordinator:
    def __init__(
        self,
        guard_payload: dict[str, Any],
        upgrade_result: dict[str, Any] | None = None,
    ) -> None:
        self._guard_payload = guard_payload
        self._upgrade_result = upgrade_result or {"success": True}
        self.preflight_calls: int = 0
        self.guard_calls: list[Any] = []
        self.upgrade_calls: list[dict[str, Any]] = []

    def deps_preflight(self) -> dict[str, Any]:
        self.preflight_calls += 1
        return {"status": "ok"}

    def deps_guard(self, preflight_path: Any | None = None) -> dict[str, Any]:
        self.guard_calls.append(preflight_path)
        return self._guard_payload

    def deps_upgrade(
        self,
        packages: list[str] | None = None,
        auto_apply: bool = False,
        generate_advice: bool = True,
    ) -> dict[str, Any]:
        self.upgrade_calls.append(
            {
                "packages": packages,
                "auto_apply": auto_apply,
                "generate_advice": generate_advice,
            }
        )
        return self._upgrade_result


def test_assess_updates_classifies_by_versions_and_reasons() -> None:
    guard = {
        "packages": [
            {"name": "pkg-major", "current": "1.2.0", "candidate": "2.0.0"},
            {"name": "pkg-minor", "current": "1.2.0", "candidate": "1.3.0"},
            {"name": "pkg-patch", "current": "1.2.0", "candidate": "1.2.1"},
            {
                "name": "pkg-major-reason",
                "current": "1.0.0",
                "candidate": "1.0.1",
                "reasons": ["Major upgrade candidate"],
            },
            {"name": "pkg-unknown", "current": None, "candidate": None},
        ]
    }
    coordinator = FakeCoordinator(guard)
    orchestrator = AutoSyncOrchestrator(
        cast(Any, coordinator),
        AutoSyncConfig(
            max_major_updates=None,
            max_minor_updates=None,
            max_patch_updates=None,
            auto_apply_safe=True,
        ),
    )

    assessment = orchestrator._assess_updates(guard)

    assert assessment.counts.major == 2
    assert assessment.counts.minor == 1
    assert assessment.counts.patch == 1
    assert assessment.packages_by_level["major"] == {"pkg-major", "pkg-major-reason"}
    assert assessment.packages_by_level["minor"] == {"pkg-minor"}
    assert assessment.packages_by_level["patch"] == {"pkg-patch"}
    assert assessment.unclassified == {"pkg-unknown"}


def test_apply_safe_updates_blocks_when_threshold_exceeded() -> None:
    guard = {
        "packages": [
            {"name": "pkg-minor", "current": "1.0.0", "candidate": "1.1.0"},
            {"name": "pkg-patch", "current": "1.0.0", "candidate": "1.0.1"},
        ]
    }
    coordinator = FakeCoordinator(guard)
    orchestrator = AutoSyncOrchestrator(
        cast(Any, coordinator),
        AutoSyncConfig(
            max_major_updates=0,
            max_minor_updates=0,
            max_patch_updates=2,
            auto_apply_safe=True,
        ),
    )
    assessment = orchestrator._assess_updates(guard)

    outcome = orchestrator._apply_safe_updates(assessment)

    assert outcome["allowed"] is False
    assert "minor" in outcome["exceedances"]
    assert outcome["applied"] is False
    assert coordinator.upgrade_calls == []


def test_execute_applies_safe_updates_when_within_threshold() -> None:
    guard = {
        "packages": [
            {"name": "pkg-one", "current": "1.0.0", "candidate": "1.0.1"},
            {"name": "pkg-two", "current": "0.9.0", "candidate": "0.9.2"},
        ]
    }
    coordinator = FakeCoordinator(guard, upgrade_result={"success": True})
    orchestrator = AutoSyncOrchestrator(
        cast(Any, coordinator),
        AutoSyncConfig(
            max_major_updates=0,
            max_minor_updates=0,
            max_patch_updates=5,
            auto_apply_safe=True,
        ),
    )

    result = orchestrator.execute()

    assert result["auto_apply"]["allowed"] is True
    assert result["auto_apply"]["applied"] is True
    assert result["auto_apply"]["packages"]["patch"] == ["pkg-one", "pkg-two"]
    assert coordinator.upgrade_calls == [
        {
            "packages": ["pkg-one", "pkg-two"],
            "auto_apply": True,
            "generate_advice": False,
        }
    ]
    assert result["auto_apply"]["plan"] == {"success": True}
