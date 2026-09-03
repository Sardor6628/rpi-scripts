#!/bin/bash
# =============================================================================
# sensorwall-firstrun.sh - collision-proof first-boot bootstrap.
#
# Works in TWO modes (see provisioning/README.md):
#
#   A) CHAINED after the Raspberry Pi Imager's own firstrun.sh (recommended,
#      because Imager already creates the login user on Bookworm). You append
#      one line to the Imager firstrun.sh that calls this script.
#
#   B) STANDALONE, launched directly from a cmdline.txt systemd.run hook when
#      you flashed without Imager OS-customisation.
#
# It is IDEMPOTENT: a marker file guarantees provisioning happens only once,
# so it is safe under either mode and safe to re-run. In standalone mode it
# also cleans its own cmdline.txt hook and reboots; when chained it lets the
# Imager firstrun.sh handle the reboot.
#
# All output is logged to /var/log/sensorwall-firstrun.log
# =============================================================================
set -uo pipefail

LOG=/var/log/sensorwall-firstrun.log
exec > >(tee -a "$LOG") 2>&1
echo "=== sensorwall first-boot bootstrap $(date) ==="

MARKER=/var/lib/sensorwall/provisioned
if [ -f "$MARKER" ]; then
    echo "Already provisioned ($MARKER present); nothing to do."
    exit 0
fi

BOOT_DIR=/boot/firmware
[ -d "$BOOT_DIR" ] || BOOT_DIR=/boot
CONF="$BOOT_DIR/sensorwall.conf"

if [ ! -f "$CONF" ]; then
    echo "ERROR: $CONF not found - cannot provision."
    exit 1
fi

# Are we the direct cmdline.txt systemd.run target (standalone mode)?
STANDALONE=0
if grep -q "sensorwall-firstrun.sh" /proc/cmdline 2>/dev/null; then
    STANDALONE=1
fi
echo "mode: $([ "$STANDALONE" = 1 ] && echo standalone || echo chained)"

# Load configuration.
set -a
# shellcheck disable=SC1090
source "$CONF"
set +a

# ---- Determine the desktop user -------------------------------------------
if [ -z "${SYSTEM_USER:-}" ]; then
    SYSTEM_USER="$(getent passwd 1000 | cut -d: -f1)"
fi
REPO_DIR="${REPO_DIR:-rpi-scripts}"
case "$REPO_DIR" in
    /*) ;;
    *) REPO_DIR="/home/$SYSTEM_USER/$REPO_DIR" ;;
esac
echo "user=$SYSTEM_USER repo=$REPO_DIR device=${DEVICE:-?}"

# ---- Hostname --------------------------------------------------------------
if [ -n "${HOSTNAME:-}" ]; then
    echo "Setting hostname to $HOSTNAME"
    raspi-config nonint do_hostname "$HOSTNAME" 2>/dev/null || \
        hostnamectl set-hostname "$HOSTNAME" || true
fi

# ---- WiFi country ----------------------------------------------------------
if [ -n "${WIFI_COUNTRY:-}" ]; then
    echo "Setting WiFi country to $WIFI_COUNTRY"
    raspi-config nonint do_wifi_country "$WIFI_COUNTRY" 2>/dev/null || \
        iw reg set "$WIFI_COUNTRY" || true
    rfkill unblock wifi || true
fi

# ---- WiFi connection (NetworkManager keyfile) ------------------------------
# Written only when it does not already exist, so an Imager-configured WiFi is
# left untouched.
if [ -n "${WIFI_SSID:-}" ]; then
    NM_FILE=/etc/NetworkManager/system-connections/sensorwall.nmconnection
    if [ ! -f "$NM_FILE" ]; then
        echo "Configuring WiFi for SSID '$WIFI_SSID'"
        mkdir -p /etc/NetworkManager/system-connections
        cat > "$NM_FILE" <<EOF
[connection]
id=sensorwall
type=wifi
autoconnect=true

[wifi]
mode=infrastructure
ssid=$WIFI_SSID

[wifi-security]
key-mgmt=wpa-psk
psk=$WIFI_PSK

[ipv4]
method=auto

[ipv6]
method=auto
EOF
        chmod 600 "$NM_FILE"
        nmcli connection reload 2>/dev/null || systemctl restart NetworkManager || true
        nmcli connection up sensorwall 2>/dev/null || true
    else
        echo "WiFi already configured; leaving existing connection in place."
    fi
fi

# ---- SSH -------------------------------------------------------------------
if [ "${ENABLE_SSH:-1}" = "1" ]; then
    echo "Enabling SSH"
    systemctl enable --now ssh 2>/dev/null || \
        systemctl enable --now sshd 2>/dev/null || true
fi

# ---- Wait for network before cloning --------------------------------------
echo "Waiting for network connectivity..."
for _ in $(seq 1 60); do
    if ping -c1 -W2 github.com >/dev/null 2>&1; then
        echo "Network is up."
        break
    fi
    sleep 2
done

# ---- Clone the repository --------------------------------------------------
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Cloning $GIT_REMOTE (branch ${GIT_BRANCH:-main})"
    apt-get update -y && apt-get install -y git || true
    sudo -u "$SYSTEM_USER" git clone -b "${GIT_BRANCH:-main}" \
        "$GIT_REMOTE" "$REPO_DIR"
fi

# ---- Provision -------------------------------------------------------------
if [ -f "$REPO_DIR/provisioning/bin/provision.sh" ]; then
    echo "Running provisioning..."
    bash "$REPO_DIR/provisioning/bin/provision.sh"
else
    echo "ERROR: provision.sh not found in cloned repo."
    exit 1
fi

# ---- Mark as provisioned ---------------------------------------------------
mkdir -p "$(dirname "$MARKER")"
date > "$MARKER"

# ---- Standalone mode: remove our cmdline hook and reboot ------------------
if [ "$STANDALONE" = 1 ]; then
    CMDLINE="$BOOT_DIR/cmdline.txt"
    if [ -f "$CMDLINE" ]; then
        echo "Removing first-boot hook from cmdline.txt"
        sed -i \
            -e 's# systemd.run=[^ ]*##g' \
            -e 's# systemd.run_success_action=[^ ]*##g' \
            -e 's# systemd.unit=kernel-command-line.target##g' \
            "$CMDLINE"
    fi
    echo "=== bootstrap complete (standalone), rebooting ==="
    sync
    reboot
else
    echo "=== bootstrap complete (chained); Imager firstrun will reboot ==="
fi
