#!/usr/bin/env bash
set -euo pipefail

VERSION="${CONTFEST_VERSION:-0.56.0}"
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$ARCH" in
x86_64 | amd64)
	ARCH="x86_64"
	;;
arm64 | aarch64)
	ARCH="arm64"
	;;
*)
	echo "Unsupported architecture: $ARCH" >&2
	exit 1
	;;
esac

TARBALL="conftest_${VERSION}_${OS}_${ARCH}.tar.gz"
URL="https://github.com/open-policy-agent/conftest/releases/download/v${VERSION}/${TARBALL}"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

curl -sSL "$URL" -o "$TMPDIR/conftest.tgz"
tar -xzf "$TMPDIR/conftest.tgz" -C "$TMPDIR"

mkdir -p bin
mv "$TMPDIR/conftest" "bin/conftest"
chmod +x "bin/conftest"

cat <<EOF
Installed conftest v${VERSION} to $(pwd)/bin/conftest
Add the following to your shell profile if not already on PATH:

    export PATH="$(pwd)/bin:$PATH"
EOF
