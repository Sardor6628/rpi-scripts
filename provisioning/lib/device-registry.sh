#!/bin/bash
# =============================================================================
# Device registry: maps the DEVICE key from sensorwall.conf to the dashboard
# that should run and the arguments it needs.
#
# Requires the config to be loaded first (sw_load_config).
# =============================================================================

# Every DEVICE key understood by sw_device_relpath.
sw_device_list() {
    echo "eagle kumgang mikeno pm_halla prikeno sen66 zinnwald"
}

# Relative path (from the repo root) of the dashboard for the selected DEVICE.
sw_device_relpath() {
    case "${DEVICE:-}" in
        eagle)    echo "Eagle_SADP3-LY2/dashboard.py" ;;
        kumgang)  echo "kumgang2/dashboard.py" ;;
        mikeno)   echo "Mikeno_SACD4_LSH_A4/dashboard.py" ;;
        pm_halla) echo "PM_Halla/dashboard.py" ;;
        prikeno)  echo "Prikeno_SACD_propane/dashboard.py" ;;
        sen66)    echo "sen66_sensorbridge/dashboard.py" ;;
        zinnwald) echo "zinnwald_sabm_analog/dashboard.py" ;;
        *)        return 1 ;;
    esac
}

# Command-line arguments for the selected DEVICE's dashboard.
sw_device_args() {
    case "${DEVICE:-}" in
        sen66)
            echo "--label ${DEVICE_LABEL:-SEN66} --port ${SEN66_PORT:-/dev/ttyUSB0} --bridge-port ${SEN66_BRIDGE_PORT:-1}"
            ;;
        zinnwald)
            echo "--label ${DEVICE_LABEL:-Zinnwald} --channel ${ZINNWALD_CHANNEL:-0} --range ${ZINNWALD_RANGE:-bip10v} --mode ${ZINNWALD_MODE:-se}"
            ;;
        *)
            echo ""
            ;;
    esac
}

# True (exit 0) for devices that talk over the Pi's hardware UART (/dev/serial0).
sw_device_uses_serial() {
    case "${DEVICE:-}" in
        eagle|mikeno|pm_halla|prikeno) return 0 ;;
        *)                             return 1 ;;
    esac
}
