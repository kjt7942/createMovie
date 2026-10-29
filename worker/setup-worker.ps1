# createMovie PC 렌더 워커 설치 (Windows 10/11)
# 1) Node.js, FFmpeg가 없으면 winget으로 설치  2) 서버 주소·토큰 입력  3) 윈도우 시작 시 자동 실행 등록
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

function Refresh-Path {
  $env:Path = "$env:ProgramFiles\nodejs;$env:LOCALAPPDATA\Microsoft\WinGet\Links;" +
    [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget-Install($id, $label) {
  if (-not (Has 'winget')) {
    Write-Host "winget이 없어 $label 을(를) 자동 설치할 수 없습니다. 직접 설치한 뒤 다시 실행해 주세요." -ForegroundColor Red
    exit 1
  }
  Write-Host "$label 설치 중… (관리자 확인 창이 뜨면 '예'를 눌러 주세요)" -ForegroundColor Cyan
  winget install -e --id $id --accept-source-agreements --accept-package-agreements --silent
  Refresh-Path
}

Write-Host "`n=== createMovie 렌더 워커 설치 ===`n" -ForegroundColor Green
Refresh-Path

# 1. Node.js 22 이상
$nodeOk = $false
if (Has 'node') { $nodeOk = [int]((node -p "process.versions.node.split('.')[0]") 2>$null) -ge 22 }
if (-not $nodeOk) { Winget-Install 'OpenJS.NodeJS.LTS' 'Node.js' }
if (-not (Has 'node')) { Write-Host 'Node.js 설치를 확인하지 못했습니다. PC를 재시작한 뒤 다시 실행해 주세요.' -ForegroundColor Red; exit 1 }
Write-Host ("Node.js " + (node -v) + " 확인")

# 2. FFmpeg
if (-not (Has 'ffmpeg')) { Winget-Install 'Gyan.FFmpeg' 'FFmpeg' }
if (Has 'ffmpeg') { Write-Host 'FFmpeg 확인' } else { Write-Host 'FFmpeg를 찾지 못했습니다. PC를 재시작한 뒤 다시 실행해 주세요.' -ForegroundColor Red; exit 1 }

# 3. 서버 주소·토큰 설정 + 렌더링 엔진 미리 받기
node "$here\worker.mjs" --setup
if ($LASTEXITCODE -ne 0) { Write-Host '설정을 마치지 못했습니다. 다시 실행해 주세요.' -ForegroundColor Red; exit 1 }

# 4. 시작 프로그램 등록(로그인하면 최소화 상태로 자동 실행)
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'createMovie 렌더 워커.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = Join-Path $here 'start-worker.bat'
$s.WorkingDirectory = $here
$s.WindowStyle = 7
$s.Save()
$desk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'createMovie 렌더 워커.lnk'
Copy-Item $lnk $desk -Force
Write-Host "`n윈도우를 켤 때 자동으로 실행되도록 등록했고, 바탕화면에 바로가기를 만들었습니다." -ForegroundColor Green

$go = Read-Host '지금 워커를 실행할까요? (Y/n)'
if ($go -ne 'n' -and $go -ne 'N') { Start-Process -FilePath (Join-Path $here 'start-worker.bat') -WorkingDirectory $here -WindowStyle Minimized }
