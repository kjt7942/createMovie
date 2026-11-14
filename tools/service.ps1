# Runs the server with no visible window. start.vbs, stop.bat and logs.bat call this. Log: jobs\server.log
param([ValidateSet('start', 'stop', 'logs')][string]$Action = 'start')

$root = Split-Path $PSScriptRoot -Parent
$log = Join-Path $root 'jobs\server.log'
$url = 'http://127.0.0.1:5100'
$listener = Get-NetTCPConnection -LocalPort 5100 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1

switch ($Action) {
    'start' {
        if ($listener) { Start-Process $url; exit 0 }  # Already running: just open the page.
        New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
        # A hidden console, not pythonw: child programs share it, so nvidia-smi, npx and ffmpeg never flash a window.
        $p = Start-Process cmd -ArgumentList "/c python -u -X utf8 server.py > `"$log`" 2>&1" -WorkingDirectory $root -WindowStyle Hidden -PassThru
        Start-Sleep 5
        if ($p.HasExited) { Start-Process notepad $log }  # It failed to start, so show why.
    }
    'stop' {
        if (-not $listener) { 'createMovie is not running.'; exit 0 }
        $q = Invoke-RestMethod "$url/api/queue" -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($q.busy -and (Read-Host "Generation is running ($($q.stage)). It will be cut off. Stop anyway? (y/n)") -ne 'y') { exit 0 }
        taskkill /PID $listener.OwningProcess /T /F | Out-Null
        'createMovie stopped.'
    }
    'logs' {
        Get-Content $log -Wait -Tail 100 -Encoding UTF8
    }
}
