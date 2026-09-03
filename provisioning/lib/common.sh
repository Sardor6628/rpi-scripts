#!/bin/bash
# =============================================================================
# Shared helpers for the sensor-wall provisioning scripts.
# Source this file; do not execute it directly.
# =============================================================================

# Location of the boot partition (Bookworm uses /boot/firmware).
sw_boot_dir() {
    if [ -d /boot/firmware ]; then
        echo /boot/firmware
    else
        echo /boot
    fi
}

# Full path of the configuration file on the boot partition.
sw_conf_path() {
    echo "$(sw_boot_dir)/sensorwall.conf"
}

sw_log() {
    echo "[sensorwall] $*"
}

# Load and export every variable from the boot-partition config file.
# Usage: sw_load_config [path]
sw_load_config() {
    local conf="${1:-$(sw_conf_path)}"
    if [ ! -f "$conf" ]; then
        sw_log "config not found: $conf"
        return 1
    fi
    set -a
    # shellcheck disable=SC1090
    source "$conf"
    set +a
}

# The desktop/login user (explicit SYSTEM_USER or the uid-1000 account).
sw_system_user() {
    if [ -n "${SYSTEM_USER:-}" ]; then
        echo "$SYSTEM_USER"
        return
    fi
    getent passwd 1000 | cut -d: -f1
}

# Home directory of the given user.
sw_user_home() {
    getent passwd "$1" | cut -d: -f6
}

# Repo root derived from this file's own location (provisioning/lib/common.sh),
# so the checkout works under any folder name.
SW_SELF_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Where the git checkout lives on the Pi. REPO_DIR in sensorwall.conf wins
# (absolute path, or a folder name relative to the user's home); otherwise the
# location of this script is used.
sw_repo_dir() {
    local user
    user="$(sw_system_user)"
    case "${REPO_DIR:-}" in
        "") echo "$SW_SELF_REPO" ;;
        /*) echo "$REPO_DIR" ;;
        *)  echo "/home/$user/$REPO_DIR" ;;
    esac
}

# Install the desktop autostart entry that launches the sensor dashboard.
# Writes an XDG autostart file (X/LXDE) and, when present, wayfire/labwc
# autostart hooks, so it works across the Bookworm desktop variants.
# Usage: sw_install_autostart <user> <exec_command>
sw_install_autostart() {
    local user="$1" exec_cmd="$2" home
    home="$(sw_user_home "$user")"

    # XDG autostart (LXDE/X, and honoured on the Pi desktop via dex).
    install -d -o "$user" -g "$user" "$home/.config/autostart"
    cat > "$home/.config/autostart/sensor-dashboard.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Sensor Dashboard
Exec=$exec_cmd
X-GNOME-Autostart-enabled=true
EOF
    chown "$user:$user" "$home/.config/autostart/sensor-dashboard.desktop"

    # wayfire compositor autostart.
    if [ -f "$home/.config/wayfire.ini" ]; then
        if ! grep -q "sensor_dashboard" "$home/.config/wayfire.ini"; then
            printf '\n[autostart]\nsensor_dashboard = %s\n' "$exec_cmd" \
                >> "$home/.config/wayfire.ini"
        fi
    fi

    # labwc compositor autostart.
    if [ -d "$home/.config/labwc" ] || command -v labwc >/dev/null 2>&1; then
        install -d -o "$user" -g "$user" "$home/.config/labwc"
        local autostart="$home/.config/labwc/autostart"
        if ! grep -q "run-dashboard" "$autostart" 2>/dev/null; then
            echo "$exec_cmd &" >> "$autostart"
        fi
        chown "$user:$user" "$autostart"
    fi
}
