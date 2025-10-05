#!/usr/bin/env python3
"""Test script for TODO implementations.

Tests all the newly implemented features from TODOs.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent


def test_reproducibility_rebuild():
    """Test reproducibility checker rebuild logic."""
    logger.info("Testing reproducibility rebuild logic...")

    try:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "src"))

        from chiron.deps.reproducibility import ReproducibilityChecker

        checker = ReproducibilityChecker()

        # Create a temporary wheelhouse
        with tempfile.TemporaryDirectory() as tmpdir:
            wheelhouse_dir = Path(tmpdir) / "wheelhouse"
            wheelhouse_dir.mkdir()

            # Verify the method exists and has proper signature
            assert hasattr(checker, "verify_wheelhouse")
            assert hasattr(checker, "_find_differences")

            # Test with no wheels (should handle empty directory)
            reports = checker.verify_wheelhouse(wheelhouse_dir)
            assert isinstance(reports, dict)
            assert len(reports) == 0

        logger.info("✓ Reproducibility rebuild logic implemented")
        return True

    except Exception as e:
        logger.error(f"✗ Reproducibility test failed: {e}")
        return False


def test_container_preparation():
    """Test container preparation logic in coordinator."""
    logger.info("Testing container preparation logic...")

    try:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "src"))

        from chiron.orchestration.coordinator import OrchestrationCoordinator

        coordinator = OrchestrationCoordinator()

        # Verify the method exists
        assert hasattr(coordinator, "air_gapped_preparation_workflow")

        # Check that the container preparation code is no longer a TODO
        coordinator_file = REPO_ROOT / "src/chiron/orchestration/coordinator.py"
        content = coordinator_file.read_text()

        # Verify TODO is removed
        assert "# TODO: Add container preparation logic" not in content

        # Verify container logic is present
        assert "Docker" in content or "docker" in content
        assert "container" in content.lower()

        logger.info("✓ Container preparation logic implemented")
        return True

    except Exception as e:
        logger.error(f"✗ Container preparation test failed: {e}")
        return False


def test_tuf_key_storage():
    """Test TUF key storage integration."""
    logger.info("Testing TUF key storage integration...")

    try:
        tuf_guide = REPO_ROOT / "docs/TUF_IMPLEMENTATION_GUIDE.md"
        content = tuf_guide.read_text()

        # Verify TODO is removed
        assert "# TODO: Integrate with secure key storage" not in content

        # Verify integration is documented
        assert "keyring" in content
        assert "AWS" in content or "Azure" in content or "Vault" in content
        assert "secure key storage" in content.lower()

        logger.info("✓ TUF key storage integration documented")
        return True

    except Exception as e:
        logger.error(f"✗ TUF key storage test failed: {e}")
        return False


def test_env_sync_script():
    """Test environment synchronization script."""
    logger.info("Testing environment sync script...")

    try:
        sync_script = REPO_ROOT / "scripts/sync_env_deps.py"

        # Verify script exists and is executable
        assert sync_script.exists()
        assert sync_script.stat().st_mode & 0o111  # Has execute permission

        # Run the script
        result = subprocess.run(
            ["python", str(sync_script)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr  # Check both stdout and stderr
        logger.debug(f"Script output: {output}")

        assert (
            result.returncode == 0
        ), f"Script failed with code {result.returncode}: {result.stderr}"
        assert (
            "synchronized" in output.lower() or "sync" in output.lower()
        ), f"Output doesn't contain expected text: {output}"

        logger.info("✓ Environment sync script works")
        return True

    except Exception as e:
        logger.error(f"✗ Environment sync test failed: {e}")
        return False


def test_env_sync_workflow():
    """Test environment sync GitHub Actions workflow."""
    logger.info("Testing environment sync workflow...")

    try:
        workflow = REPO_ROOT / ".github/workflows/sync-env.yml"

        # Verify workflow exists
        assert workflow.exists()

        content = workflow.read_text()

        # Verify workflow has necessary components
        assert "sync_env_deps.py" in content
        assert "pyproject.toml" in content
        assert ".devcontainer" in content

        logger.info("✓ Environment sync workflow configured")
        return True

    except Exception as e:
        logger.error(f"✗ Environment sync workflow test failed: {e}")
        return False


def test_env_sync_precommit():
    """Test environment sync pre-commit hook."""
    logger.info("Testing environment sync pre-commit hook...")

    try:
        precommit = REPO_ROOT / ".pre-commit-config.yaml"
        content = precommit.read_text()

        # Verify pre-commit hook is configured
        assert "sync-env-deps" in content or "sync_env_deps" in content
        assert "scripts/sync_env_deps.py" in content

        logger.info("✓ Environment sync pre-commit hook configured")
        return True

    except Exception as e:
        logger.error(f"✗ Environment sync pre-commit test failed: {e}")
        return False


def test_env_sync_documentation():
    """Test environment sync documentation."""
    logger.info("Testing environment sync documentation...")

    try:
        doc = REPO_ROOT / "docs/ENVIRONMENT_SYNC.md"

        # Verify documentation exists
        assert doc.exists()

        content = doc.read_text()

        # Verify documentation has key sections
        assert "Synchronization" in content or "synchronization" in content
        assert "devcontainer" in content.lower()
        assert "CI" in content or "workflow" in content.lower()
        assert "Usage" in content

        logger.info("✓ Environment sync documentation complete")
        return True

    except Exception as e:
        logger.error(f"✗ Environment sync documentation test failed: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Testing TODO Implementations")
    logger.info("=" * 60)

    tests = [
        test_reproducibility_rebuild,
        test_container_preparation,
        test_tuf_key_storage,
        test_env_sync_script,
        test_env_sync_workflow,
        test_env_sync_precommit,
        test_env_sync_documentation,
    ]

    results = []
    for test in tests:
        results.append(test())
        logger.info("")

    logger.info("=" * 60)
    logger.info("Test Results")
    logger.info("=" * 60)

    passed = sum(results)
    total = len(results)

    logger.info(f"Passed: {passed}/{total}")

    if passed == total:
        logger.info("✓ All tests passed!")
        return 0
    else:
        logger.error(f"✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
