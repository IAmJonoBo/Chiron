# Makefile for Chiron development

.PHONY: help install dev test lint format security build clean release wheelhouse airgap verify doctor serve docs deptry
.PHONY: policy-check policy-bundle

PYTEST_SEED ?= $(shell date +%s)
PYTEST_CMD = PYTEST_RANDOMLY_SEED=$(PYTEST_SEED) uv run pytest

# Default target
help: ## Show this help message
	@echo "Chiron Development Commands"
	@echo "========================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync --all-extras --dev

dev: install ## Set up development environment
	uv run pre-commit install
	@echo "✅ Development environment ready!"

test: ## Run tests
	$(PYTEST_CMD)

test-all: ## Run all tests including slow ones
	$(PYTEST_CMD) --cov-report=html --cov-report=xml -m ""

lint: ## Run linting
	uv run pre-commit run --all-files

format: ## Format code
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

security: ## Run security scans
	uv run bandit -r src/
	uv run safety check
	@if command -v grype &> /dev/null; then grype .; else echo "Install grype for vulnerability scanning"; fi

build: ## Build package
	uv build

clean: ## Clean build artifacts
	rm -rf dist/
	rm -rf wheelhouse/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

release: ## Create a release
	uv run chiron release

wheelhouse: ## Create wheelhouse bundle
	uv run chiron wheelhouse

airgap: ## Create air-gapped bundle
	uv run chiron airgap pack

verify: ## Verify artifacts
	uv run chiron verify

doctor: ## Run health checks
	uv run chiron doctor

serve: ## Start development server
	uv run chiron serve --reload

docs: ## Start documentation server
	uv run mkdocs serve

policy-check: ## Evaluate OPA/conftest policies locally
	scripts/run_policy_checks.sh

policy-bundle: ## Build reusable OPA policy bundle
	scripts/build_opa_bundle.sh

# CI/CD helpers
ci-test: ## Run CI tests
	$(PYTEST_CMD) --cov-report=xml

ci-security: ## Run CI security scans
	uv run bandit -r src/ -f json -o bandit-report.json
	uv run safety check --json --output safety-report.json

ci-build: ## Build for CI
	uv build
	syft . -o cyclonedx-json=sbom.json
	syft . -o spdx-json=sbom-spdx.json

# Container targets
container-build: ## Build container
	docker build -t chiron:latest .

container-run: ## Run container
	docker run -p 8000:8000 chiron:latest

# Development shortcuts
quick-test: ## Run quick tests only
	$(PYTEST_CMD) -x --ff

watch-test: ## Run tests in watch mode
	uv run pytest-watch

mypy: ## Run type checking
	uv run mypy src/

deptry: ## Detect unused and undeclared dependencies
	uv run deptry --config pyproject.toml src/chiron tests

coverage: ## Generate coverage report
	$(PYTEST_CMD) --cov-report=html
	@echo "Coverage report generated in htmlcov/"

benchmark: ## Run performance benchmarks
	uv run pytest tests/ -m benchmark --benchmark-only

sync-env: ## Sync dev and CI environment dependencies
	python scripts/sync_env_deps.py

diff-cover: ## Run diff-cover on changed lines (requires coverage.xml)
	uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=80

mutmut-run: ## Run mutation testing
	uv run mutmut run

mutmut-results: ## Show mutation testing results
	uv run mutmut results

mutmut-html: ## Generate mutation testing HTML report
	uv run mutmut html
