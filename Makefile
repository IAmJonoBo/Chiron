.PHONY: bootstrap check build release wheelhouse airgap verify clean help

# Python interpreter
PYTHON ?= python3

# uv for package management
UV ?= uv

help:
	@echo "Chiron - Air-gapped Python wheelhouse builder"
	@echo ""
	@echo "Available targets:"
	@echo "  bootstrap   - Install uv, dev dependencies, and pre-commit hooks"
	@echo "  check       - Run linting (ruff, mypy) and tests"
	@echo "  build       - Build Python package (wheel and sdist)"
	@echo "  release     - Prepare release artifacts (build + checksums)"
	@echo "  wheelhouse  - Create wheelhouse with all dependencies"
	@echo "  airgap      - Create airgap bundle for offline installation"
	@echo "  verify      - Verify airgap bundle integrity"
	@echo "  clean       - Remove build artifacts and caches"

bootstrap:
	@echo "==> Installing uv..."
	@command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
	@echo "==> Installing development dependencies..."
	$(UV) pip install -e ".[dev]"
	@echo "==> Installing pre-commit hooks..."
	pre-commit install
	@echo "==> Bootstrap complete!"

check:
	@echo "==> Running ruff..."
	ruff check src/ tests/
	@echo "==> Running ruff format check..."
	ruff format --check src/ tests/
	@echo "==> Running mypy..."
	mypy src/
	@echo "==> Running pytest..."
	pytest
	@echo "==> All checks passed!"

build:
	@echo "==> Building package..."
	$(PYTHON) -m build
	@echo "==> Build complete! Artifacts in dist/"

release: clean build
	@echo "==> Creating release artifacts..."
	@cd dist && sha256sum * > SHA256SUMS
	@echo "==> Release artifacts ready in dist/"
	@ls -lh dist/

wheelhouse:
	@echo "==> Creating wheelhouse..."
	@mkdir -p wheelhouse
	$(UV) pip download -d wheelhouse -r requirements.txt || true
	$(UV) pip download -d wheelhouse chiron || $(UV) pip download -d wheelhouse .
	@echo "==> Wheelhouse created in wheelhouse/"
	@ls -lh wheelhouse/

airgap: wheelhouse
	@echo "==> Creating airgap bundle..."
	@mkdir -p airgap-bundles
	@tar -czf airgap-bundles/chiron-airgap-$$(date +%Y%m%d-%H%M%S).tar.gz \
		wheelhouse/ \
		requirements.txt \
		OFFLINE.md \
		README.md
	@echo "==> Airgap bundle created in airgap-bundles/"
	@ls -lh airgap-bundles/

verify:
	@echo "==> Verifying airgap bundle..."
	@if [ -z "$$(ls -A airgap-bundles/*.tar.gz 2>/dev/null)" ]; then \
		echo "Error: No airgap bundle found. Run 'make airgap' first."; \
		exit 1; \
	fi
	@latest=$$(ls -t airgap-bundles/*.tar.gz | head -1); \
	echo "Verifying $$latest..."; \
	tar -tzf $$latest > /dev/null && echo "✓ Bundle is valid" || echo "✗ Bundle is corrupted"
	@echo "==> Verification complete!"

clean:
	@echo "==> Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info/ wheelhouse/ .pytest_cache/ .coverage htmlcov/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "==> Clean complete!"
