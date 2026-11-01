# Keeps the RTX 3070 Ti display alive during local H3 generation. Self-elevates via UAC.
# TDR values need one reboot to apply; power and clock limits reset on every reboot, so rerun this after booting.
param([int]$PowerLimit = 220, [int]$MaxClock = 1800)

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    $p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -PowerLimit $PowerLimit -MaxClock $MaxClock"
    exit $p.ExitCode
}

$fail = 0
$key = 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers'
Set-ItemProperty $key -Name TdrDelay -Value 60 -Type DWord
Set-ItemProperty $key -Name TdrDdiDelay -Value 60 -Type DWord
nvidia-smi -pl $PowerLimit | Out-Null
if ($LASTEXITCODE -ne 0) { $fail = 1 }
nvidia-smi -lgc "300,$MaxClock" | Out-Null
if ($LASTEXITCODE -ne 0) { $fail = 1 }
exit $fail
