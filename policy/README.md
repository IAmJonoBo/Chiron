# Policy-as-Code Bundle

This directory contains Open Policy Agent (OPA) policies used to enforce
Chiron's supply-chain and workflow governance requirements. Policies are
executed with [`conftest`](https://github.com/open-policy-agent/conftest)
from developer machines (via pre-commit) and in CI quality gates.

## Layout

```
policy/
├── README.md
├── policies/
│   ├── dependencies.rego   # SBOM freshness and dependency hygiene
│   └── workflows.rego      # GitHub workflow invariants
└── bundle/                 # (optional) compiled bundles produced by opa build
```

Policies expect contextual input emitted by `scripts/policy_context.py`. The
script inspects dependency manifests, SBOM artifacts, and Git metadata to
calculate freshness signals consumed by the Rego rules.

## Running locally

```bash
scripts/run_policy_checks.sh
```

The helper script ensures `conftest` is available, generates the input payload,
and evaluates the policy set across:

1. Dynamic context (`policy_context.py`)
2. GitHub workflow definitions (`.github/workflows/*.yml`)

To rebuild a distributable bundle (used by downstream consumers), run:

```bash
scripts/build_opa_bundle.sh
```

That command creates `policy/bundle/policy.tar.gz`, which may be distributed to
other environments that consume the same policy pack.
