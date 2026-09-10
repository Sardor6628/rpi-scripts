<#
.SYNOPSIS
    Switch which sensor dashboard a sensor-wall Raspberry Pi runs.

.DESCRIPTION
    Rewrites DEVICE (and optionally DEVICE_LABEL) in sensorwall.conf on the SD
    card's boot partition. Insert the card in this PC, run the script, put the
    card back in the Pi and boot: sensor-update.service applies the new
    dashboard automatically.

.EXAMPLE
    .\Set-SensorDevice.ps1 -Device pm_halla -Label 'Halla Wall'

.EXAMPLE
    .\Set-SensorDevice.ps1 -Device zinnwald -ConfPath E:\sensorwall.conf
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('eagle', 'kumgang', 'mikeno', 'pm_halla', 'prikeno', 'sen66', 'zinnwald')]
    [string]$Device,

    [string]$Label,

    [string]$ConfPath
)

$ErrorActionPreference = 'Stop'

if (-not $ConfPath) {
    $found = Get-PSDrive -PSProvider FileSystem |
        ForEach-Object { Join-Path $_.Root 'sensorwall.conf' } |
        Where-Object { Test-Path $_ }
    if ($found.Count -eq 0) {
        throw 'No sensorwall.conf found on any mounted drive. Insert the SD card or pass -ConfPath.'
    }
    if ($found.Count -gt 1) {
        throw "Several candidates found ($($found -join ', ')). Pass -ConfPath to pick one."
    }
    $ConfPath = $found[0]
}

if (-not (Test-Path $ConfPath)) { throw "Not found: $ConfPath" }

function Set-ConfValue([string[]]$Lines, [string]$Key, [string]$Value) {
    $pattern = "^\s*$([regex]::Escape($Key))="
    $replaced = $false
    $out = @(foreach ($line in $Lines) {
        if ($line -match $pattern) { $replaced = $true; "$Key=$Value" } else { $line }
    })
    if (-not $replaced) { $out += "$Key=$Value" }
    return $out
}

$lines = Get-Content $ConfPath
$lines = Set-ConfValue $lines 'DEVICE' $Device
if ($Label) { $lines = Set-ConfValue $lines 'DEVICE_LABEL' $Label }
Set-Content -Path $ConfPath -Value $lines

Write-Host "DEVICE=$Device$(if ($Label) { " / DEVICE_LABEL=$Label" }) written to $ConfPath"
Write-Host 'Eject the card, put it back in the Pi and reboot.'
