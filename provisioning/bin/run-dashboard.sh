#!/bin/bash
# =============================================================================
# Launches the dashboard for the configured DEVICE inside the desktop session.
#
# Started automatically at login by the autostart entry that provision.sh
# installs. Restarts the dashboard if it exits (e.g. sensor unplugged).
# =============================================================================
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../lib/common.sh
source "$DIR/../lib/common.sh"
# shellcheck source=../lib/device-registry.sh
source "$DIR/../lib/device-registry.sh"

sw_load_config || exit 1

REPO="$(sw_repo_dir)"
REL="$(sw_device_relpath)" || { sw_log "unknown DEVICE='${DEVICE:-}'"; exit 1; }
ARGS="$(sw_device_args)"

cd "$REPO" || { sw_log "repo not found: $REPO"; exit 1; }
# shellcheck disable=SC1091
source "$REPO/venv/bin/activate"

sw_log "starting dashboard: $REL $ARGS"
while true; do
    # shellcheck disable=SC2086
    python "$REL" $ARGS
    code=$?
    sw_log "dashboard exited (code $code); restarting in 5s"
    sleep 5
done
