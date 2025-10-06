#!/usr/bin/env bash
set -euo pipefail

if ! command -v opa >/dev/null 2>&1; then
	echo "opa CLI not found. Install from https://www.openpolicyagent.org/docs/latest/#running-opa" >&2
	exit 1
fi

mkdir -p policy/bundle
opa build policy -b policy -o policy/bundle/policy.tar.gz

echo "Bundle written to policy/bundle/policy.tar.gz"
