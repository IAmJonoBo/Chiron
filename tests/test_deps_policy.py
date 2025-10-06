"""Regression and coverage tests for chiron.deps.policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from chiron.deps.policy import (
    DependencyPolicy,
    PackagePolicy,
    PolicyEngine,
    PolicyViolation,
    load_policy,
)


def test_load_policy_missing_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING")
    config_path = tmp_path / "missing-policy.toml"
    policy = DependencyPolicy.from_toml(config_path)
    assert policy.default_allowed is True
    assert "Policy config not found" in caplog.text


def test_load_policy_parses_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "policy.toml"
    config_path.write_text(
        """
[dependency_policy]
default_allowed = false
max_major_version_jump = 0
require_security_review = true
allow_pre_releases = true
python_version_requirement = "python>=3.11"

[dependency_policy.allowlist.demo]
version_ceiling = "2.0.0"
allowed_versions = ["1.0.0", "2.0.0"]
blocked_versions = ["1.5.0"]
upgrade_cadence_days = 30
requires_review = true
reason = "Pinned for compliance"

[dependency_policy.denylist.legacy]
reason = "Security freeze"
        """
    )

    policy = DependencyPolicy.from_toml(config_path)
    assert policy.default_allowed is False
    assert policy.max_major_version_jump == 0
    assert policy.allow_pre_releases is True
    assert policy.python_version_requirement == "python>=3.11"
    assert "demo" in policy.allowlist
    assert policy.allowlist["demo"].requires_review is True
    assert policy.denylist["legacy"].reason == "Security freeze"


def test_check_package_allowed_paths() -> None:
    policy = DependencyPolicy(
        default_allowed=False,
        allowlist={"demo": PackagePolicy(name="demo")},
        denylist={"legacy": PackagePolicy(name="legacy", allowed=False, reason="Nope")},
    )
    engine = PolicyEngine(policy)

    assert engine.check_package_allowed("legacy") == (False, "Nope")
    assert engine.check_package_allowed("demo") == (True, None)
    assert engine.check_package_allowed("unknown") == (
        False,
        "Package not in allowlist and default policy is deny",
    )


def test_check_version_allowed_combinations() -> None:
    policy = DependencyPolicy(
        allow_pre_releases=False,
        allowlist={
            "demo": PackagePolicy(
                name="demo",
                allowed_versions=["1.0.0"],
                blocked_versions=["0.9.0"],
                version_ceiling="1.0.0",
                version_floor="0.5.0",
            )
        },
    )
    engine = PolicyEngine(policy)

    assert engine.check_version_allowed("other", "1.2.3") == (True, None)
    assert engine.check_version_allowed("demo", "garbage")[0] is False
    assert engine.check_version_allowed("demo", "0.9.0") == (False, "Version 0.9.0 is blocked")
    assert engine.check_version_allowed("demo", "1.0.0") == (True, None)
    assert engine.check_version_allowed("demo", "1.2.0")[0] is False
    assert engine.check_version_allowed("demo", "0.1.0")[0] is False

    # Remove allow/block lists to exercise the pre-release gate explicitly.
    policy.allowlist["demo"].allowed_versions.clear()
    policy.allowlist["demo"].blocked_versions.clear()
    assert engine.check_version_allowed("demo", "1.0.0rc1") == (
        False,
        "Pre-release versions not allowed",
    )


def test_check_upgrade_allowed_denied_by_package() -> None:
    policy = DependencyPolicy(
        default_allowed=True,
        denylist={"blocked": PackagePolicy(name="blocked", allowed=False, reason="Blocked")},
    )
    engine = PolicyEngine(policy)
    violations = engine.check_upgrade_allowed("blocked", "1.0.0", "1.1.0")
    assert violations == [
        PolicyViolation(
            package="blocked",
            current_version="1.0.0",
            target_version="1.1.0",
            violation_type="package_denied",
            message="Blocked",
            severity="error",
        )
    ]


def test_check_upgrade_allowed_combines_violations(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = DependencyPolicy(
        default_allowed=True,
        default_upgrade_cadence_days=10,
        max_major_version_jump=0,
        allowlist={
            "demo": PackagePolicy(
                name="demo",
                version_ceiling="2.0.0",
                upgrade_cadence_days=14,
                requires_review=True,
            )
        },
    )
    engine = PolicyEngine(policy)
    engine.record_upgrade("demo")
    engine._last_upgrade_timestamps["demo"] = datetime.now(UTC) - timedelta(days=5)

    violations = engine.check_upgrade_allowed("demo", "1.0.0", "3.0.0")
    types = {v.violation_type for v in violations}
    assert types == {"version_denied", "major_version_jump", "upgrade_cadence", "review_required"}


def test_record_upgrade_tracks_timestamp() -> None:
    policy = DependencyPolicy()
    engine = PolicyEngine(policy)
    engine.record_upgrade("demo")
    assert "demo" in engine._last_upgrade_timestamps
    assert isinstance(engine._last_upgrade_timestamps["demo"], datetime)


def test_load_policy_helper_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = tmp_path / "configs" / "dependency-policy.toml"
    sample.parent.mkdir()
    sample.write_text("[dependency_policy]\n")
    monkeypatch.chdir(tmp_path)

    loaded = load_policy()
    assert isinstance(loaded, DependencyPolicy)
