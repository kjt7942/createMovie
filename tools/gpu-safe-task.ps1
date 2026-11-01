# Registers a startup task that reapplies the GPU limits after every boot, so gpu-safe.ps1 needs no UAC prompt.
# Run once. The task calls nvidia-smi directly so that it does not depend on this drive being mounted at boot.
# gpu-safe.ps1 rewrites this task's numbers whenever new limits are applied. Remove with: Unregister-ScheduledTask -TaskName H3-GPU-Safe
param([int]$PowerLimit = 220, [int]$MaxClock = 1800)

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    $p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -PowerLimit $PowerLimit -MaxClock $MaxClock"
    if (-not $p) { exit 1 }  # The UAC prompt was declined.
    exit $p.ExitCode
}

$steps = @()
if ($PowerLimit -gt 0) { $steps += "nvidia-smi -pl $PowerLimit" }
if ($MaxClock -gt 0) { $steps += "nvidia-smi -lgc 300,$MaxClock" }
if (-not $steps) { exit 0 }  # This card allows neither limit, so there is nothing to reapply at boot.
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c ' + ($steps -join ' && '))
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = 'PT1M'  # The NVIDIA driver may not be ready the moment Windows starts.
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName 'H3-GPU-Safe' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'H3-GPU-Safe'
Start-Sleep -Seconds 5
exit (Get-ScheduledTaskInfo -TaskName 'H3-GPU-Safe').LastTaskResult
