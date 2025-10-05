#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC2034
SCRIPT_NAME="manage-deps.sh"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "${REPO_ROOT}" || exit 1

RUN_LOCK=true
RUN_SYNC=false
RUN_PREFLIGHT=false
DRY_RUN=false
PREFLIGHT_SUMMARY=""
PREFLIGHT_ARGS_ENV="${MANAGE_DEPS_PREFLIGHT_ARGS-}"
LOCK_FILE="${MANAGE_DEPS_LOCK_PATH:-uv.lock}"
DEFAULT_PREFLIGHT_SUMMARY="vendor/wheelhouse/allowlisted-sdists.json"
EXTRA_PREFLIGHT_ARGS=()

usage() {
	cat <<'EOF'
Usage: manage-deps.sh [OPTIONS] [-- PRE_FLIGHT_ARGS...]

Regenerate dependency artifacts after version bumps and optionally run
hardening checks. The script is designed for Renovate post-upgrade tasks
but is equally useful for local workflows.

Options:
  --dry-run                Print the actions without executing them
  --no-lock                Skip running `uv lock`
  --sync                   Run `uv sync --all-extras --dev` after locking
  --no-sync                Skip syncing even if MANAGE_DEPS_RUN_SYNC is set
  --preflight              Execute dependency preflight validation
  --preflight-json PATH    Write allowlist summary JSON to PATH
  --lock-file PATH         Path to the lock file (default: uv.lock)
  -h, --help               Show this message and exit
  --                       Treat the remaining arguments as preflight extras

Environment Variables:
  UV_LOCK_ARGS                 Extra arguments (word-split) for `uv lock`
  UV_SYNC_ARGS                 Extra arguments (word-split) for `uv sync`
  MANAGE_DEPS_RUN_SYNC         When "1", "true", or "yes" enables --sync
  MANAGE_DEPS_PREFLIGHT_ARGS   Extra args appended to the preflight command
  MANAGE_DEPS_LOCK_PATH        Override the lock file location
  PYTHON_BIN                   Python interpreter to use (default: python3, fallback python)

Examples:
  bash scripts/manage-deps.sh --preflight
  bash scripts/manage-deps.sh --sync --preflight -- --exit-zero
  MANAGE_DEPS_RUN_SYNC=1 bash scripts/manage-deps.sh
EOF
}

log() {
	printf '[manage-deps] %s\n' "$1"
}

print_cmd() {
	local -a cmd=("$@")
	local rendered
	printf -v rendered '%q ' "${cmd[@]}"
	log "Running: ${rendered% }"
}

run_cmd() {
	local -a cmd=("$@")
	print_cmd "${cmd[@]}"
	if [[ ${DRY_RUN} == true ]]; then
		return 0
	fi
	"${cmd[@]}"
}

ensure_command() {
	local binary="$1"
	if ! command -v "${binary}" >/dev/null 2>&1; then
		echo "${binary} is required but was not found in PATH" >&2
		exit 1
	fi
}

truthy() {
	case "${1-}" in
	1 | true | TRUE | yes | YES | on | ON) return 0 ;;
	*) return 1 ;;
	esac
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--dry-run)
		DRY_RUN=true
		shift
		;;
	--no-lock)
		RUN_LOCK=false
		shift
		;;
	--sync)
		RUN_SYNC=true
		shift
		;;
	--no-sync)
		RUN_SYNC=false
		shift
		;;
	--preflight)
		RUN_PREFLIGHT=true
		shift
		;;
	--preflight-json)
		if [[ $# -lt 2 ]]; then
			echo "--preflight-json requires a path argument" >&2
			exit 1
		fi
		RUN_PREFLIGHT=true
		PREFLIGHT_SUMMARY="$2"
		shift 2
		;;
	--lock-file)
		if [[ $# -lt 2 ]]; then
			echo "--lock-file requires a path argument" >&2
			exit 1
		fi
		LOCK_FILE="$2"
		shift 2
		;;
	-h | --help)
		usage
		exit 0
		;;
	--)
		shift
		EXTRA_PREFLIGHT_ARGS=("$@")
		break
		;;
	*)
		echo "Unknown option: $1" >&2
		usage >&2
		exit 1
		;;
	esac

done

if truthy "${MANAGE_DEPS_RUN_SYNC-}"; then
	RUN_SYNC=true
fi

if truthy "${MANAGE_DEPS_RUN_PREFLIGHT-}"; then
	RUN_PREFLIGHT=true
fi

if [[ ${#EXTRA_PREFLIGHT_ARGS[@]} -gt 0 ]] && [[ ${RUN_PREFLIGHT} != true ]]; then
	RUN_PREFLIGHT=true
fi

if [[ -z ${PREFLIGHT_SUMMARY} ]]; then
	PREFLIGHT_SUMMARY="${DEFAULT_PREFLIGHT_SUMMARY}"
fi

LOCK_ARGS=()
if [[ -n ${UV_LOCK_ARGS-} ]]; then
	# shellcheck disable=SC2206
	LOCK_ARGS=(${UV_LOCK_ARGS})
fi

SYNC_ARGS=()
if [[ -n ${UV_SYNC_ARGS-} ]]; then
	# shellcheck disable=SC2206
	SYNC_ARGS=(${UV_SYNC_ARGS})
elif [[ ${RUN_SYNC} == true ]]; then
	SYNC_ARGS=(--all-extras --dev)
fi

PREFLIGHT_ARGS=()
if [[ -n ${PREFLIGHT_ARGS_ENV} ]]; then
	# shellcheck disable=SC2206
	PREFLIGHT_ARGS+=(${PREFLIGHT_ARGS_ENV})
fi
if [[ ${#EXTRA_PREFLIGHT_ARGS[@]} -gt 0 ]]; then
	PREFLIGHT_ARGS+=("${EXTRA_PREFLIGHT_ARGS[@]}")
fi

if [[ (${RUN_LOCK} == true) || (${RUN_SYNC} == true) ]] && [[ ${DRY_RUN} != true ]]; then
	ensure_command uv
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
	PYTHON_BIN="python"
fi

if [[ ${RUN_PREFLIGHT} == true ]]; then
	if [[ ${DRY_RUN} != true ]]; then
		ensure_command "${PYTHON_BIN}"
		if [[ ! -f ${LOCK_FILE} ]]; then
			echo "Lock file '${LOCK_FILE}' not found. Run 'uv lock' or pass --lock-file." >&2
			exit 1
		fi
	fi
fi

if [[ ${RUN_LOCK} == true ]]; then
	run_cmd uv lock "${LOCK_ARGS[@]}"
fi

if [[ ${RUN_SYNC} == true ]]; then
	if [[ ${#SYNC_ARGS[@]} -eq 0 ]]; then
		SYNC_ARGS=(--all-extras --dev)
	fi
	run_cmd uv sync "${SYNC_ARGS[@]}"
fi

if [[ ${RUN_PREFLIGHT} == true ]]; then
	mkdir -p "$(dirname "${PREFLIGHT_SUMMARY}")"
	PREFLIGHT_CMD=("${PYTHON_BIN}")
	if [[ -f "scripts/preflight_deps.py" ]]; then
		PREFLIGHT_CMD+=("scripts/preflight_deps.py")
	else
		PREFLIGHT_CMD+=(-m "chiron.deps.preflight")
	fi
	PREFLIGHT_CMD+=(--lock "${LOCK_FILE}" --allowlist-summary "${PREFLIGHT_SUMMARY}" --json)
	if [[ ${#PREFLIGHT_ARGS[@]} -gt 0 ]]; then
		PREFLIGHT_CMD+=("${PREFLIGHT_ARGS[@]}")
	fi
	run_cmd "${PREFLIGHT_CMD[@]}"
fi

if [[ ${DRY_RUN} == true ]]; then
	log "Dry run complete"
	exit 0
fi

git status --short
log "Dependency management complete"
