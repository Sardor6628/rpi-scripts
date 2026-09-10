#!/bin/bash
# =============================================================================
# set-device.sh - switch which sensor dashboard this Raspberry Pi runs.
#
#   sudo provisioning/bin/set-device.sh pm_halla
#   sudo provisioning/bin/set-device.sh pm_halla "Halla Wall"
#   sudo provisioning/bin/set-device.sh pm_halla --reboot
#
# Rewrites DEVICE (and optionally DEVICE_LABEL) in sensorwall.conf on the boot
# partition. With --apply the new autostart is installed right away, otherwise
# sensor-update.service picks it up on the next boot.
# =============================================================================
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PROV="$(cd "$DIR/.." && pwd)"
# shellcheck source=../lib/common.sh
source "$DIR/../lib/common.sh"
# shellcheck source=../lib/device-registry.sh
source "$DIR/../lib/device-registry.sh"

usage() {
    echo "Usage: sudo $0 <device> [label] [--apply|--reboot]"
    echo "Devices: $(sw_device_list)"
    exit 1
}

NEW_DEVICE=""
NEW_LABEL=""
ACTION=""
for arg in "$@"; do
    case "$arg" in
        --apply)   ACTION=apply ;;
        --reboot)  ACTION=reboot ;;
        -h|--help) usage ;;
        -*)        echo "unknown option: $arg"; usage ;;
        *)
            if [ -z "$NEW_DEVICE" ]; then
                NEW_DEVICE="$arg"
            elif [ -z "$NEW_LABEL" ]; then
                NEW_LABEL="$arg"
            else
                usage
            fi
            ;;
    esac
done

[ -n "$NEW_DEVICE" ] || usage

if ! DEVICE="$NEW_DEVICE" sw_device_relpath >/dev/null; then
    echo "unknown device '$NEW_DEVICE'"
    usage
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "must run as root (the config lives on the boot partition)"
    exit 1
fi

CONF="$(sw_conf_path)"
sw_conf_set DEVICE "$NEW_DEVICE" "$CONF" || exit 1
[ -n "$NEW_LABEL" ] && sw_conf_set DEVICE_LABEL "$NEW_LABEL" "$CONF"
sw_log "device set to '$NEW_DEVICE' in $CONF"

case "$ACTION" in
    apply)
        sw_load_config || exit 1
        sw_install_autostart "$(sw_system_user)" "/bin/bash $PROV/bin/run-dashboard.sh"
        sw_log "autostart updated; log out or reboot to start the new dashboard"
        ;;
    reboot)
        sw_log "rebooting"
        sync
        reboot
        ;;
    *)
        sw_log "reboot to start the new dashboard"
        ;;
esac
