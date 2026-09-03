# Sensor Wall Provisioning

Fully hands-off setup for the sensor-wall Raspberry Pis. After flashing the OS
you drop **two files** on the boot partition and add **one hook**; on first boot
the Pi configures itself: WiFi, hostname, SSH, all system + Python dependencies,
the correct sensor dashboard on the screen, and a git-based update mechanism.

## The 7 devices

Set `DEVICE` in `sensorwall.conf` to one of:

| `DEVICE`   | Folder                  | Dashboard                    | Interface        |
|------------|-------------------------|------------------------------|------------------|
| `eagle`    | `Eagle_SADP3-LY2`       | `dashboard.py`               | UART `/dev/serial0` |
| `kumgang`  | `kumgang2`              | `dashboard.py`               | USB SensorBridge |
| `mikeno`   | `Mikeno_SACD4_LSH_A4`   | `dashboard.py`               | UART `/dev/serial0` |
| `pm_halla` | `PM_Halla`              | `dashboard.py`               | UART `/dev/serial0` |
| `prikeno`  | `Prikeno_SACD_propane`  | `dashboard.py`               | UART `/dev/serial0` |
| `sen66`    | `sen66_sensorbridge`    | `dashboard.py`               | USB SensorBridge |
| `zinnwald` | `zinnwald_sabm_analog`  | `dashboard.py`               | MCC USB DAQ      |

---

## Step 1 — Flash the OS

Flash **Raspberry Pi OS (Bookworm, Desktop)** with Raspberry Pi Imager.

In the Imager's **OS customisation** dialog, set at least the **username and
password** (Bookworm requires a login user; this becomes `SYSTEM_USER`). You may
also set WiFi/hostname there — this provisioner leaves any WiFi you already
configured in place. Setting anything here makes Imager generate its own
`firstrun.sh`, which we chain onto in Step 3 (Path A).

## Step 2 — Copy the config + bootstrap onto the boot partition

The boot partition is the small FAT volume that appears in Explorer/Finder after
flashing. Copy these two files from `provisioning/boot/`:

- `sensorwall-firstrun.sh`
- `sensorwall.conf.example` → rename to **`sensorwall.conf`** and edit it
  (`DEVICE`, `DEVICE_LABEL`, WiFi, `GIT_REMOTE`, …).

## Step 3 — Wire the first-boot hook

Pick the path that matches how you flashed.

### Path A — you set a user (or anything) in Imager  *(recommended)*

Imager created a `firstrun.sh` on the boot partition. Add one line to it, just
before its final `exit 0`, so it calls our bootstrap after Imager's own setup:

```
bash /boot/firmware/sensorwall-firstrun.sh
```

> If the boot partition mounts as `/boot` (not `/boot/firmware`), use that path.

### Path B — plain flash, no Imager customisation  *(advanced)*

There is no `firstrun.sh`. Add the systemd hook to `cmdline.txt` (a **single
line** — append at the end, space-separated, no newline):

```
systemd.run=/boot/firmware/sensorwall-firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target
```

> On Bookworm you still need a login user. Without Imager customisation, create
> `userconf.txt` on the boot partition, otherwise the desktop shows the
> first-run wizard and autologin won't work.

## Step 4 — Boot

The first boot runs the bootstrap once (logged to
`/var/log/sensorwall-firstrun.log`): it connects WiFi, clones the repo, installs
everything, registers the dashboard autostart, then reboots into the dashboard.
No keyboard or SSH needed. The bootstrap is idempotent — a marker at
`/var/lib/sensorwall/provisioned` prevents it from ever running twice.

### PowerShell helper (Windows, Path A)

With the boot partition mounted as e.g. `E:`:

```powershell
# copy bootstrap + config
Copy-Item .\provisioning\boot\sensorwall-firstrun.sh E:\sensorwall-firstrun.sh
Copy-Item .\provisioning\boot\sensorwall.conf.example E:\sensorwall.conf
# ...edit E:\sensorwall.conf...

# chain our bootstrap onto the Imager firstrun.sh (insert before its exit 0)
$fr   = 'E:\firstrun.sh'
$hook = 'bash /boot/firmware/sensorwall-firstrun.sh'
$body = Get-Content $fr
if ($body -notcontains $hook) {
    ($body -replace '^exit 0\s*$', "$hook`nexit 0") | Set-Content $fr
}
```

---

## Switching the sensor type later

Edit `DEVICE` (and any label/overrides) in `sensorwall.conf` on the boot
partition, then reboot. `sensor-update.service` re-applies the autostart for the
new device on every boot — no re-flash required.

## Updating the code from git

Create an empty file named **`update`** on the boot partition and reboot:

```powershell
New-Item -ItemType File E:\update
```

On the next boot the Pi pulls the latest `GIT_BRANCH`, re-runs `setup.sh` for any
new dependencies, deletes the flag, and starts the refreshed dashboard.

## What gets installed

`provision.sh` runs the repo's `setup.sh` (system packages, shared `venv`,
`libuldaq`, all `requirements.txt`, MCC udev rule), adds the user to
`dialout`/`plugdev`, enables the hardware UART for serial devices, sets desktop
autologin, installs `sensor-update.service`, and registers the dashboard
autostart.

## Files

```
provisioning/
  boot/
    sensorwall-firstrun.sh   # first-boot bootstrap (copy to boot partition)
    sensorwall.conf.example  # config template (copy as sensorwall.conf)
  bin/
    provision.sh             # one-time provisioning (run by the bootstrap)
    run-dashboard.sh         # launches + respawns the dashboard at login
    update-check.sh          # boot-flag git update + autostart re-apply
  lib/
    common.sh                # shared helpers (config, autostart)
    device-registry.sh       # DEVICE -> dashboard mapping
  systemd/
    sensor-update.service    # runs update-check.sh on every boot
```

## Troubleshooting

- **First-boot log:** `cat /var/log/sensorwall-firstrun.log`
- **Force a re-provision:** `sudo rm /var/lib/sensorwall/provisioned`, then
  `sudo bash /boot/firmware/sensorwall-firstrun.sh` (or reboot in Path B).
- **Update/apply log:** `journalctl -u sensor-update.service`
- **Serial permission denied:** confirm the user is in `dialout` and, for UART
  devices, that the serial console is disabled (`raspi-config`).
- **No SensorBridge:** `ls /dev/ttyUSB*` — adjust `SEN66_PORT` if needed.
- **Dashboard not showing:** ensure the Pi booted to **Desktop autologin**
  (`raspi-config` → System Options → Boot / Auto Login → Desktop Autologin).
