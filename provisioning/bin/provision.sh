#!/bin/bash
# =============================================================================
# provision.sh - one-time setup of a sensor-wall Raspberry Pi.
#
# Called by the first-boot bootstrap (boot/firstrun.sh) as root, after the
# repository has been cloned and the network is up. Safe to re-run.
# =============================================================================
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PROV="$(cd "$DIR/.." && pwd)"
# shellcheck source=../lib/common.sh
source "$DIR/../lib/common.sh"
# shellcheck source=../lib/device-registry.sh
source "$DIR/../lib/device-registry.sh"

sw_load_config || exit 1

USER_NAME="$(sw_system_user)"
REPO="$(sw_repo_dir)"

sw_log "provisioning device='${DEVICE:-}' user='$USER_NAME' repo='$REPO'"

# 1. Base install: system packages, shared venv, libuldaq, requirements, udev.
sw_log "running setup.sh (system packages + virtualenv + dependencies)"
bash "$REPO/setup.sh"
chown -R "$USER_NAME:$USER_NAME" "$REPO"

# 2. Hardware-access groups for USB serial / SensorBridge / DAQ.
usermod -aG dialout,plugdev "$USER_NAME" || true

# 3. Serial (LIN) devices need the hardware UART with the console detached.
if sw_device_uses_serial; then
    sw_log "enabling hardware UART for serial device"
    raspi-config nonint do_serial_cons 1 || true
    raspi-config nonint do_serial_hw 0 || true
fi

# 4. Boot straight into the desktop, logged in (fullscreen dashboards need X).
raspi-config nonint do_boot_behaviour B4 || true

# 5. Install the apply/update-on-boot service.
SERVICE=/etc/systemd/system/sensor-update.service
sed "s#__RUN_UPDATE__#$PROV/bin/update-check.sh#g" \
    "$PROV/systemd/sensor-update.service" > "$SERVICE"
systemctl daemon-reload
systemctl enable sensor-update.service || true

# 6. Autostart the dashboard in the desktop session.
sw_install_autostart "$USER_NAME" "$PROV/bin/run-dashboard.sh"

sw_log "provisioning complete"
