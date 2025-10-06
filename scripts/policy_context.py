#!/usr/bin/env python3
"""Compute contextual signals for policy enforcement."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

DEPENDENCY_FILES: Sequence[str] = (
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "scripts/manage-deps.sh",
)
SBOM_FILES: Sequence[str] = ("sbom.json", "sbom-spdx.json")


@dataclass
class FileStatus:
    path: str
    exists: bool
    mtime: float | None
    staged: bool

    def to_payload(self) -> dict:
        payload = {
            "path": self.path,
            "exists": self.exists,
            "staged": self.staged,
        }
        if self.exists and self.mtime is not None:
            payload["mtime"] = _dt.datetime.fromtimestamp(
                self.mtime, tz=_dt.UTC
            ).isoformat()
        return payload


def _git_diff_names(args: Iterable[str]) -> list[str]:
    try:
        result = subprocess.run(
            ("git", "diff", "--name-only", *args),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []

    if result.returncode not in (0, 1):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def staged_paths() -> set[str]:
    return set(_git_diff_names(["--cached"]))


def baseline_diff_paths() -> set[str]:
    """Detect file changes compared to an inferred base reference."""
    env = os.environ
    base_ref = env.get("POLICY_BASE_REF") or env.get("GITHUB_BASE_REF")

    # Pushed branches don't expose GITHUB_BASE_REF, fall back to main
    inferred = base_ref or "origin/main"

    # Attempt a three-dot diff if base exists; otherwise fall back to HEAD^ for merge commits.
    candidates: list[Sequence[str]] = []

    if inferred:
        if not inferred.startswith("origin/"):
            inferred = f"origin/{inferred}"
        candidates.append((f"{inferred}...HEAD",))

    # Handle freshly created branches where remote main may not exist locally.
    candidates.extend((("HEAD^", "HEAD"), ("HEAD~1", "HEAD")))

    for cand in candidates:
        names = _git_diff_names(cand)
        if names:
            return set(names)
    return set()


def collect_status(paths: Sequence[str], staged: set[str]) -> list[FileStatus]:
    statuses: list[FileStatus] = []
    for path in paths:
        exists = os.path.exists(path)
        mtime = os.path.getmtime(path) if exists else None
        statuses.append(FileStatus(path, exists, mtime, path in staged))
    return statuses


def compute_payload() -> dict:
    staged = staged_paths()
    baseline = baseline_diff_paths()
    dependency_statuses = collect_status(DEPENDENCY_FILES, staged)

    sbom_statuses = collect_status(SBOM_FILES, staged)
    now = _dt.datetime.now(tz=_dt.UTC)

    dependency_mtimes = [
        status.mtime for status in dependency_statuses if status.exists and status.mtime
    ]
    latest_dependency_mtime = max(dependency_mtimes) if dependency_mtimes else None

    sbom_info = {
        "files": [status.to_payload() for status in sbom_statuses],
        "exists": any(status.exists for status in sbom_statuses),
        "staged": any(status.staged for status in sbom_statuses),
        "fresh_vs_dependencies": True,
        "fresh_within_days": True,
        "older_than_dependencies": False,
        "baseline_changed": bool(
            {status.path for status in dependency_statuses if status.path in baseline}
        ),
    }

    if latest_dependency_mtime is not None:
        sbom_mt = max((status.mtime or 0.0) for status in sbom_statuses)
        if sbom_mt == 0.0:
            sbom_info["fresh_vs_dependencies"] = False
            sbom_info["older_than_dependencies"] = True
        else:
            sbom_info["fresh_vs_dependencies"] = sbom_mt >= latest_dependency_mtime
            sbom_info["older_than_dependencies"] = sbom_mt < latest_dependency_mtime

    freshness_window = _dt.timedelta(days=7)
    for status in sbom_statuses:
        if status.exists and status.mtime is not None:
            generated_at = _dt.datetime.fromtimestamp(status.mtime, tz=_dt.UTC)
            stale = now - generated_at > freshness_window
            if stale:
                sbom_info["fresh_within_days"] = False
                break
    else:
        sbom_info["fresh_within_days"] = sbom_info["exists"]

    dependency_payload = {
        "files": [status.to_payload() for status in dependency_statuses],
        "staged": any(status.staged for status in dependency_statuses),
        "baseline_diff": bool(
            {status.path for status in dependency_statuses if status.path in baseline}
        ),
        "latest_mtime": latest_dependency_mtime,
    }

    return {
        "kind": "context",
        "timestamp": now.isoformat(),
        "sbom": sbom_info,
        "dependencies": dependency_payload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate JSON context for OPA policies"
    )
    parser.add_argument(
        "--output", "-o", help="Write JSON payload to path instead of stdout"
    )
    args = parser.parse_args()

    payload = compute_payload()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    else:
        json.dump(payload, fp=os.sys.stdout, indent=2, sort_keys=True)
        os.sys.stdout.write("\n")


if __name__ == "__main__":
    main()
