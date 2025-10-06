"""Automated dependency synchronization safeguards."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from packaging.version import InvalidVersion, Version

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from chiron.orchestration.coordinator import OrchestrationCoordinator

logger = logging.getLogger(__name__)

SEMVER_MAJOR = "major"
SEMVER_MINOR = "minor"
SEMVER_PATCH = "patch"
SEMVER_ORDER = {
    SEMVER_PATCH: 0,
    SEMVER_MINOR: 1,
    SEMVER_MAJOR: 2,
}


@dataclass(slots=True)
class AutoSyncConfig:
    """Configuration controlling automated dependency synchronization."""

    max_major_updates: int | None = 0
    max_minor_updates: int | None = 0
    max_patch_updates: int | None = 0
    auto_apply_safe: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_major_updates",
            self._sanitize_limit(self.max_major_updates, "max_major_updates"),
        )
        object.__setattr__(
            self,
            "max_minor_updates",
            self._sanitize_limit(self.max_minor_updates, "max_minor_updates"),
        )
        object.__setattr__(
            self,
            "max_patch_updates",
            self._sanitize_limit(self.max_patch_updates, "max_patch_updates"),
        )
        object.__setattr__(self, "auto_apply_safe", bool(self.auto_apply_safe))

    @staticmethod
    def _sanitize_limit(value: int | None, field_name: str) -> int | None:
        if value is None:
            return None
        try:
            coerced = int(value)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError(f"{field_name} must be an integer or None") from exc
        if coerced < 0:
            logger.debug("Clamping %s to 0 (received %s)", field_name, coerced)
            return 0
        return coerced

    def get_limit(self, level: str) -> int | None:
        """Return the configured limit for the given semver level."""

        if level not in {SEMVER_MAJOR, SEMVER_MINOR, SEMVER_PATCH}:  # pragma: no cover
            raise ValueError(f"Unsupported semver level: {level}")
        value = getattr(self, f"max_{level}_updates")
        return cast(int | None, value)


@dataclass(slots=True)
class UpdateCounts:
    """Summary of candidate updates grouped by semver impact."""

    major: int = 0
    minor: int = 0
    patch: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            SEMVER_MAJOR: self.major,
            SEMVER_MINOR: self.minor,
            SEMVER_PATCH: self.patch,
        }


@dataclass(slots=True)
class UpdateAssessment:
    """Structured representation of guard findings for auto-sync decisions."""

    counts: UpdateCounts
    packages_by_level: dict[str, set[str]] = field(
        default_factory=lambda: {
            SEMVER_MAJOR: set(),
            SEMVER_MINOR: set(),
            SEMVER_PATCH: set(),
        }
    )
    unclassified: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": self.counts.as_dict(),
            "packages": {
                level: sorted(packages)
                for level, packages in self.packages_by_level.items()
            },
            "unclassified": sorted(self.unclassified),
        }


class AutoSyncOrchestrator:
    """Coordinates automated dependency synchronization with guard-enforced limits."""

    def __init__(
        self,
        coordinator: OrchestrationCoordinator,
        config: AutoSyncConfig | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._config = config or AutoSyncConfig()

    def execute(self) -> dict[str, Any]:
        """Run the auto-sync workflow respecting configured safeguards."""

        logger.info("Starting automated dependency sync workflow")

        preflight = self._coordinator.deps_preflight()
        guard = self._coordinator.deps_guard()
        assessment = self._assess_updates(guard)
        auto_apply = self._apply_safe_updates(assessment)

        return {
            "preflight": preflight,
            "guard": guard,
            "assessment": assessment.to_dict(),
            "auto_apply": auto_apply,
        }

    def _assess_updates(self, guard: Mapping[str, Any]) -> UpdateAssessment:
        """Analyse upgrade guard output and classify candidate updates."""

        packages = guard.get("packages") if isinstance(guard, Mapping) else None
        counts = UpdateCounts()
        result = UpdateAssessment(counts=counts)

        if not isinstance(packages, Iterable):
            logger.debug("Guard payload missing package list; nothing to assess")
            return result

        for entry in packages:
            if not isinstance(entry, Mapping):
                continue
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            level = self._classify_package(entry)
            if level == SEMVER_MAJOR:
                counts.major += 1
                result.packages_by_level[SEMVER_MAJOR].add(name)
            elif level == SEMVER_MINOR:
                counts.minor += 1
                result.packages_by_level[SEMVER_MINOR].add(name)
            elif level == SEMVER_PATCH:
                counts.patch += 1
                result.packages_by_level[SEMVER_PATCH].add(name)
            else:
                result.unclassified.add(name)

        return result

    def _apply_safe_updates(self, assessment: UpdateAssessment) -> dict[str, Any]:
        """Apply safe upgrades when thresholds allow."""

        allowed, exceedances = self._within_thresholds(assessment.counts)
        packages = {
            level: sorted(names)
            for level, names in assessment.packages_by_level.items()
        }

        outcome: dict[str, Any] = {
            "allowed": allowed,
            "applied": False,
            "packages": packages,
            "exceedances": exceedances,
        }

        if not allowed:
            outcome["reason"] = "update thresholds exceeded"
            return outcome

        if not self._config.auto_apply_safe:
            outcome["reason"] = "auto-apply disabled"
            return outcome

        safe_candidates = packages.get(SEMVER_PATCH, [])
        if not safe_candidates:
            outcome["reason"] = "no safe updates available"
            return outcome

        logger.info(
            "Applying %s safe updates: %s",
            len(safe_candidates),
            ", ".join(safe_candidates),
        )
        plan = self._coordinator.deps_upgrade(
            packages=safe_candidates,
            auto_apply=True,
            generate_advice=False,
        )
        outcome["applied"] = True
        outcome["plan"] = plan
        return outcome

    def _within_thresholds(
        self, counts: UpdateCounts
    ) -> tuple[bool, dict[str, dict[str, int | None]]]:
        exceedances: dict[str, dict[str, int | None]] = {}
        for level in (SEMVER_MAJOR, SEMVER_MINOR, SEMVER_PATCH):
            limit = self._config.get_limit(level)
            value = getattr(counts, level)
            if limit is not None and value > limit:
                exceedances[level] = {"count": value, "limit": limit}
        return (not exceedances, exceedances)

    def _classify_package(self, package: Mapping[str, Any]) -> str | None:
        current = str(package.get("current") or "").strip() or None
        candidate = str(package.get("candidate") or "").strip() or None
        reasons = package.get("reasons")

        level = self._classify_by_version(current, candidate)
        reason_level = None
        if isinstance(reasons, Iterable):
            reason_level = self._classify_by_reasons(reasons)

        if reason_level and (
            level is None or SEMVER_ORDER[reason_level] > SEMVER_ORDER.get(level, -1)
        ):
            level = reason_level

        return level

    @staticmethod
    def _classify_by_version(current: str | None, candidate: str | None) -> str | None:
        if not current or not candidate:
            return None
        try:
            cur = Version(current)
            nxt = Version(candidate)
        except InvalidVersion:
            return None

        if nxt <= cur:
            return None

        cur_release = list(cur.release) + [0] * max(0, 3 - len(cur.release))
        nxt_release = list(nxt.release) + [0] * max(0, 3 - len(nxt.release))
        cur_major, cur_minor, cur_patch = cur_release[:3]
        nxt_major, nxt_minor, nxt_patch = nxt_release[:3]

        if nxt_major > cur_major:
            return SEMVER_MAJOR
        if nxt_major == cur_major and nxt_minor > cur_minor:
            return SEMVER_MINOR
        if nxt_major == cur_major and nxt_minor == cur_minor and nxt_patch > cur_patch:
            return SEMVER_PATCH

        # Handle post/dev releases as patch-level adjustments
        if nxt > cur:
            return SEMVER_PATCH
        return None

    @staticmethod
    def _classify_by_reasons(reasons: Iterable[Any]) -> str | None:
        for raw in reasons:
            text = str(raw or "").lower()
            if "upgrade" not in text and "upgrade type" not in text:
                continue
            if "major" in text:
                return SEMVER_MAJOR
            if "minor" in text:
                return SEMVER_MINOR
            if "patch" in text:
                return SEMVER_PATCH
        return None
