# Supply-Chain (deps) Modules Status & Roadmap

## Overview

The `chiron.deps` package contains supply-chain management modules for dependency governance, reproducibility, security, and policy enforcement. This document tracks implementation status and testing progress.

## Module Status

| Module                 | Lines | Status | Test Coverage | Priority | Notes                                                                         |
| ---------------------- | ----- | ------ | ------------- | -------- | ----------------------------------------------------------------------------- |
| `__init__.py`          | 27    | 🟢     | Included      | Low      | Package initialization                                                        |
| `constraints.py`       | 235   | 🟡     | Partial (62%) | High     | Hash-pinned constraints generation - subprocess_utils integrated, tests added |
| `policy.py`            | 323   | 🟡     | Partial (75%) | High     | Policy engine for governance - tests added for core functionality             |
| `bundler.py`           | 277   | 🟢     | **98%**       | Medium   | **NEW**: Dependency bundling for airgap - 12 comprehensive tests added        |
| `verify.py`            | 197   | 🟡     | None          | Medium   | Pipeline verification script                                                  |
| `signing.py`           | 223   | 🔴     | Omitted       | Medium   | Artifact signing with cosign/sigstore                                         |
| `preflight_summary.py` | 138   | 🔴     | Omitted       | Medium   | Preflight check summaries                                                     |
| `drift.py`             | 251   | 🔴     | Omitted       | Medium   | Dependency drift detection                                                    |
| `graph.py`             | 269   | 🔴     | Omitted       | Low      | Dependency graph analysis                                                     |
| `supply_chain.py`      | 279   | 🔴     | Omitted       | High     | Core supply chain orchestration                                               |
| `upgrade_advisor.py`   | 381   | 🔴     | Omitted       | Medium   | Upgrade recommendations                                                       |
| `conflict_resolver.py` | 395   | 🔴     | Omitted       | Medium   | Dependency conflict resolution                                                |
| `private_mirror.py`    | 445   | 🔴     | Omitted       | Low      | Private PyPI mirror management                                                |
| `safe_upgrade.py`      | 457   | 🔴     | Omitted       | Medium   | Safe upgrade workflows                                                        |
| `security_overlay.py`  | 476   | 🔴     | Omitted       | High     | Security scanning integration                                                 |
| `guard.py`             | 1650  | 🔴     | Omitted       | High     | Upgrade guard policies                                                        |
| `mirror_manager.py`    | 565   | 🔴     | Omitted       | Low      | Mirror management                                                             |
| `oci_packaging.py`     | 498   | 🔴     | Omitted       | Medium   | OCI artifact packaging                                                        |
| `planner.py`           | 736   | 🔴     | Omitted       | Medium   | Upgrade planning                                                              |
| `preflight.py`         | 704   | 🔴     | Omitted       | Medium   | Preflight checks                                                              |
| `reproducibility.py`   | 626   | 🔴     | Omitted       | High     | Reproducibility verification                                                  |
| `status.py`            | 480   | 🔴     | Omitted       | Low      | Status reporting                                                              |
| `sync.py`              | 716   | 🔴     | Omitted       | Medium   | Dependency synchronization                                                    |

**Total Lines**: ~10,334 lines across 26 modules

## Recent Progress

### Phase 1: Infrastructure Improvements ✅

- Created `subprocess_utils` module for robust command execution
- Integrated subprocess_utils into `constraints.py`
- Added comprehensive tests for `constraints.py` and `policy.py`
- Updated coverage configuration to explicitly list deps modules

### Phase 2: Testing Foundation (In Progress)

- ✅ Added 50+ tests for policy engine functionality
- ✅ Added 30+ tests for constraints generation
- ✅ **NEW (Jan 2026)**: Added 12 tests for bundler.py (98% coverage)
- ✅ Removed bundler.py from coverage omit list
- ⏳ Need integration tests for end-to-end workflows
- ⏳ Need subprocess mocking for remaining modules

## Testing Strategy

### High Priority Modules (Target: 70%+ coverage)

1. **policy.py** - ✅ Core tests completed (75%)
   - Package policy validation
   - Version constraints checking
   - Upgrade policy enforcement
2. **constraints.py** - ✅ Core tests completed (62%)
   - Constraints generation with uv
   - Constraints generation with pip-tools
   - Hash generation
   - Extras handling
3. **bundler.py** - ✅ **COMPLETE (98%)**
   - BundleMetadata class
   - WheelhouseBundler initialization
   - Bundle creation with wheels
   - SBOM/OSV inclusion
   - Checksum generation

4. **supply_chain.py** - 🔴 Not started
   - Core orchestration logic
   - Integration with other modules
   - End-to-end workflows

5. **security_overlay.py** - 🔴 Not started
   - Vulnerability scanning
   - Security policy enforcement
   - SBOM integration

6. **reproducibility.py** - 🔴 Not started
   - Reproducibility checks
   - Wheel comparison
   - Hash verification

### Medium Priority Modules (Target: 50%+ coverage)

1. **bundler.py** - ✅ **COMPLETE (98%)**
2. **safe_upgrade.py** - 🔴 Not started
3. **upgrade_advisor.py** - 🔴 Not started
4. **conflict_resolver.py** - 🔴 Not started
5. **drift.py** - 🔴 Not started
6. **signing.py** - 🔴 Not started

### Lower Priority Modules (Target: 30%+ coverage)

- verify.py
- preflight_summary.py
- graph.py
- private_mirror.py
- mirror_manager.py
- status.py
- sync.py
- oci_packaging.py
- planner.py
- preflight.py

## Integration Points

### External Tools Required

- **uv**: Package management and constraints generation
- **pip-tools**: Alternative constraints generation
- **syft**: SBOM generation
- **cosign**: Artifact signing
- **grype**: Vulnerability scanning

All external tool calls should use `chiron.subprocess_utils` for:

- Executable path resolution
- Timeout handling
- Error handling with actionable messages
- Binary availability checking

### Subprocess Utils Migration Status

- ✅ constraints.py - Migrated to subprocess_utils
- ✅ bundler.py - Migrated to subprocess_utils
- 🔴 signing.py - Still uses raw subprocess
- 🔴 Other modules - Need audit and migration

## Coverage Goals

### Current Status

- **Overall Project**: 63.06% (exceeds 50% gate ✅)
- **Deps Modules**: ~70% average for tested modules (policy 75%, constraints 62%, bundler 98%)
- **Target**: 65%+ overall, 60%+ for all high-priority deps modules

### Milestone Targets

#### Milestone 1: Core Testing ✅ **COMPLETE**

- ✅ policy.py: 75% coverage
- ✅ constraints.py: 62% coverage
- ✅ bundler.py: 98% coverage
- Target overall: 63.06% ✅ **ACHIEVED**

#### Milestone 2: High Priority Modules (Current)

- supply_chain.py: 60%+ coverage
- security_overlay.py: 60%+ coverage
- reproducibility.py: 60%+ coverage (or remove from omit if already implemented)
- Target overall: 64-66%

#### Milestone 3: Medium Priority Modules

- ✅ bundler.py: 98% coverage **COMPLETE**
- safe_upgrade.py: 50%+ coverage
- upgrade_advisor.py: 50%+ coverage
- conflict_resolver.py: 50%+ coverage
- Target overall: 66-68%

#### Milestone 4: Complete Coverage

- All modules: 50%+ coverage
- Target overall: 70%+ (Frontier Grade 🎯)

## Testing Patterns

### Unit Tests

```python
# Test configuration objects
def test_config_creation():
    config = ModuleConfig(param1="value1")
    assert config.param1 == "value1"

# Test validation logic
def test_validation_rules():
    engine = ValidationEngine()
    result = engine.validate(input_data)
    assert result.is_valid
```

### Integration Tests

```python
# Test subprocess integration
@patch("chiron.subprocess_utils.run_subprocess")
def test_subprocess_call(mock_run):
    mock_run.return_value = CompletedProcess(returncode=0)
    result = module.execute_command(["uv", "pip", "list"])
    assert result.success

# Test end-to-end workflows
def test_end_to_end_workflow(tmp_path):
    # Setup
    config = setup_test_environment(tmp_path)
    # Execute
    result = run_workflow(config)
    # Verify
    assert result.status == "success"
```

### Property-Based Tests

```python
from hypothesis import given
from hypothesis import strategies as st

@given(st.text(), st.integers())
def test_property(text_input, int_input):
    result = module.process(text_input, int_input)
    # Property: result should always be valid
    assert module.validate(result)
```

## Documentation Needs

### Module Documentation

- [ ] Add comprehensive docstrings to all public functions
- [ ] Document all configuration options
- [ ] Add usage examples to module docstrings
- [ ] Document integration points with external tools

### User Guides

- [ ] Dependency governance guide
- [ ] Reproducibility workflow guide
- [ ] Security scanning integration guide
- [ ] Airgap deployment guide

### Developer Guides

- [ ] Testing strategy guide
- [ ] Subprocess utils migration guide
- [ ] Adding new policy types
- [ ] Extending the policy engine

## Next Steps

### Immediate (This Sprint)

1. ✅ Complete policy.py and constraints.py tests
2. ✅ Integrate subprocess_utils into constraints.py
3. ⏳ Create this tracking document
4. ⏳ Update IMPLEMENTATION_SUMMARY.md with progress

### Short Term (Next Sprint)

1. Add tests for supply_chain.py core orchestration
2. Add tests for security_overlay.py
3. Add tests for reproducibility.py
4. Migrate signing.py to subprocess_utils
5. Target 58-60% overall coverage

### Medium Term (2-3 Sprints)

1. Complete medium priority module testing
2. Add integration tests for end-to-end workflows
3. Document all modules comprehensively
4. Target 65%+ overall coverage

### Long Term (Frontier Grade)

1. Complete all module testing
2. Add property-based tests for complex logic
3. Add contract tests for external tool integration
4. Target 70%+ overall coverage
5. Achieve frontier-grade quality across the board

## Known Issues & Technical Debt

### Code Quality

- [ ] Many modules use raw subprocess calls instead of subprocess_utils
- [ ] Inconsistent error handling across modules
- [ ] Some modules have complex functions that need refactoring
- [ ] Limited type hints in older modules

### Testing Gaps

- [ ] No integration tests for end-to-end workflows
- [ ] Limited error path testing
- [ ] No property-based tests for complex validation logic
- [ ] Mock objects could be more comprehensive

### Documentation Technical Debt

- [ ] Many modules lack comprehensive docstrings
- [ ] Configuration options not fully documented
- [ ] Limited usage examples
- [ ] No architectural overview document

## Success Metrics

### Quality Gates

- ✅ Minimum coverage: 50% (currently 63.06%)
- ⏳ Target coverage: 65% (currently 63.06%)
- 🎯 Frontier coverage: 70%

### Test Count

- Current: ~599 tests
- Target for 65% coverage: ~620 tests
- Target for 70% coverage: ~700 tests

### Module Maturity

- 🟢 Green (70%+ coverage): 3 modules (policy, bundler, plus **init**.py at 100%)
- 🟡 Yellow (50-70% coverage): 1 module (constraints at 62%)
- 🔴 Red (<50% coverage): 20 modules

### Documentation

- Module docs: 10% complete
- User guides: 20% complete
- Developer guides: 30% complete
- API docs: 40% complete

## Contributing

When adding tests to deps modules:

1. Use `chiron.subprocess_utils` for all subprocess calls
2. Add comprehensive unit tests for core logic
3. Add integration tests for subprocess interactions
4. Update this document with progress
5. Remove module from omit list in pyproject.toml when >50% coverage
6. Update IMPLEMENTATION_SUMMARY.md status table

## References

- [subprocess_utils module](../src/chiron/subprocess_utils.py)
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
- [CHIRON_UPGRADE_PLAN.md](../CHIRON_UPGRADE_PLAN.md)
- [Quality Gates Workflow](../.github/workflows/quality-gates.yml)
