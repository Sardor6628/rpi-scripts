#!/bin/bash
# =============================================================================
# update-check.sh - runs on every boot (via sensor-update.service).
#
#   * If an update flag file is present on the boot partition, it pulls the
#     latest code from git and re-runs setup.sh to pick up new dependencies.
#   * Always re-applies the dashboard autostart from the current config, so you
#     can switch the sensor type simply by editing sensorwall.conf and
#     rebooting.
#
# Trigger an update: create an (empty) file named `update` on the boot
# partition and reboot.
# =============================================================================
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PROV="$(cd "$DIR/.." && pwd)"
# shellcheck source=../lib/common.sh
source "$DIR/../lib/common.sh"
# shellcheck source=../lib/device-registry.sh
source "$DIR/../lib/device-registry.sh"

sw_load_config || exit 0

USER_NAME="$(sw_system_user)"
REPO="$(sw_repo_dir)"
BOOT="$(sw_boot_dir)"

# ----------------------------------------------------------------------------
# Git update, gated by a boot-partition flag file.
# ----------------------------------------------------------------------------
FLAG=""
for name in update update.flag UPDATE; do
    if [ -f "$BOOT/$name" ]; then
        FLAG="$BOOT/$name"
        break
    fi
done

if [ -n "$FLAG" ]; then
    sw_log "update flag found ($FLAG) -> pulling latest from git"
    if [ -d "$REPO/.git" ]; then
        sw_git_auth_begin "$USER_NAME"
        sw_git "$USER_NAME" -C "$REPO" fetch --all --prune || true
        sw_git "$USER_NAME" -C "$REPO" reset --hard "origin/${GIT_BRANCH:-main}" || true
        sw_git_auth_end
    fi
    sw_log "re-running setup.sh for any new dependencies"
    bash "$REPO/setup.sh" || true
    chown -R "$USER_NAME:$USER_NAME" "$REPO"
    rm -f "$FLAG"
    sw_log "update complete"
fi

# ----------------------------------------------------------------------------
# Always re-apply the dashboard autostart from the current config.
# ----------------------------------------------------------------------------
sw_install_autostart "$USER_NAME" "/bin/bash $PROV/bin/run-dashboard.sh"
