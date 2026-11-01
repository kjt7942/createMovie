# Keeps the RTX 3070 Ti display alive during local H3 generation. Self-elevates via UAC.
# TDR values need one reboot to apply; power and clock limits reset on every reboot, so rerun this after booting.
# The defaults are for that card. The service passes numbers fitted to the installed card; 0 leaves a limit alone.
param([int]$PowerLimit = 220, [int]$MaxClock = 1800)

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    $p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -PowerLimit $PowerLimit -MaxClock $MaxClock"
    if (-not $p) { exit 1 }  # The UAC prompt was declined.
    exit $p.ExitCode
}

$fail = 0
$key = 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers'
Set-ItemProperty $key -Name TdrDelay -Value 60 -Type DWord
Set-ItemProperty $key -Name TdrDdiDelay -Value 60 -Type DWord
if ($PowerLimit -gt 0) {
    nvidia-smi -pl $PowerLimit | Out-Null
    if ($LASTEXITCODE -ne 0) { $fail = 1 }
}
if ($MaxClock -gt 0) {
    nvidia-smi -lgc "300,$MaxClock" | Out-Null
    if ($LASTEXITCODE -ne 0) { $fail = 1 }
}
# The startup task must reapply these numbers, not the ones it was registered with.
if (Get-ScheduledTask -TaskName 'H3-GPU-Safe' -ErrorAction SilentlyContinue) {
    $steps = @()
    if ($PowerLimit -gt 0) { $steps += "nvidia-smi -pl $PowerLimit" }
    if ($MaxClock -gt 0) { $steps += "nvidia-smi -lgc 300,$MaxClock" }
    if ($steps) { Set-ScheduledTask -TaskName 'H3-GPU-Safe' -Action (New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c ' + ($steps -join ' && '))) | Out-Null }
}
exit $fail
