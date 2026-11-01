# Registers a startup task that reapplies the GPU limits after every boot, so gpu-safe.ps1 needs no UAC prompt.
# Run once. The task calls nvidia-smi directly so that it does not depend on this drive being mounted at boot.
# Keep these numbers in step with gpu-safe.ps1. Remove with: Unregister-ScheduledTask -TaskName H3-GPU-Safe
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    $p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if (-not $p) { exit 1 }  # The UAC prompt was declined.
    exit $p.ExitCode
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c nvidia-smi -pl 220 && nvidia-smi -lgc 300,1800'
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = 'PT1M'  # The NVIDIA driver may not be ready the moment Windows starts.
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName 'H3-GPU-Safe' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'H3-GPU-Safe'
Start-Sleep -Seconds 5
exit (Get-ScheduledTaskInfo -TaskName 'H3-GPU-Safe').LastTaskResult
