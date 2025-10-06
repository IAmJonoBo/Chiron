#!/usr/bin/env bash
set -euo pipefail

CONTFEST_BIN=${CONTFEST_BIN-}

if [[ -z ${CONTFEST_BIN} ]]; then
	if [[ -x "$(pwd)/bin/conftest" ]]; then
		CONTFEST_BIN="$(pwd)/bin/conftest"
	else
		CONTFEST_BIN=$(command -v conftest || true)
	fi
fi

if [[ -z ${CONTFEST_BIN} ]]; then
	echo "conftest binary not found. Install it via 'scripts/install_conftest.sh' or https://github.com/open-policy-agent/conftest/releases" >&2
	exit 1
fi

# Ensure the temporary file carries a .json extension for conftest auto-detection
TMPDIR_PATH="${TMPDIR:-/tmp}"
TMP_JSON=$(mktemp "${TMPDIR_PATH}/policy_ctx.XXXXXX.json")
trap 'rm -f "$TMP_JSON"' EXIT

python3 scripts/policy_context.py --output "$TMP_JSON"

"${CONTFEST_BIN}" test "$TMP_JSON" --policy policy
"${CONTFEST_BIN}" test .github/workflows --policy policy --all-namespaces
