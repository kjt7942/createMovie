# createMovie 설치(Windows 10/11). 이미 있는 것은 건너뛰므로 여러 번 실행해도 안전하다.
# -H3: 묻지 않고 AI 영상 생성 도구까지 설치
param([switch]$H3)
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

function Refresh-Path {
  $env:Path = "$env:ProgramFiles\nodejs;$env:ProgramFiles\Git\cmd;$env:LOCALAPPDATA\Microsoft\WinGet\Links;" +
    [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Fail($text) { Write-Host $text -ForegroundColor Red; exit 1 }
function Winget-Install($id, $label) {
  if (-not (Has 'winget')) { Fail "winget이 없어 $label 을(를) 자동 설치할 수 없습니다. 직접 설치한 뒤 다시 실행해 주세요." }
  Write-Host "$label 설치 중… (관리자 확인 창이 뜨면 '예'를 눌러 주세요)" -ForegroundColor Cyan
  winget install -e --id $id --accept-source-agreements --accept-package-agreements --silent
  Refresh-Path
}
function Python-Ok {
  if (-not (Has 'python')) { return $false }
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
  return $LASTEXITCODE -eq 0
}
function Node-Ok {
  if (-not (Has 'node')) { return $false }
  return [int](node -p "process.versions.node.split('.')[0]") -ge 22
}

Write-Host "`n=== createMovie 설치 ===`n" -ForegroundColor Green
Refresh-Path

if (-not (Python-Ok)) { Winget-Install 'Python.Python.3.12' 'Python' }
if (-not (Python-Ok)) { Fail 'Python을 찾지 못했습니다. 이 창을 닫고 새로 열어 다시 실행해 주세요.' }
Write-Host ((python --version) + ' 확인')

if (-not (Node-Ok)) { Winget-Install 'OpenJS.NodeJS.LTS' 'Node.js' }
if (-not (Node-Ok)) { Fail 'Node.js 22 이상을 찾지 못했습니다. 이 창을 닫고 새로 열어 다시 실행해 주세요.' }
Write-Host ('Node.js ' + (node -v) + ' 확인')

if (-not ((Has 'ffmpeg') -and (Has 'ffprobe'))) { Winget-Install 'Gyan.FFmpeg' 'FFmpeg' }
if (-not (Has 'ffmpeg')) { Fail 'FFmpeg를 찾지 못했습니다. 이 창을 닫고 새로 열어 다시 실행해 주세요.' }
Write-Host 'FFmpeg 확인'

if (-not (Has 'git')) { Winget-Install 'Git.Git' 'Git' }

Write-Host "`nPython 패키지 설치 중…" -ForegroundColor Cyan
python -m pip install --disable-pip-version-check -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail 'Python 패키지 설치에 실패했습니다.' }

Write-Host '영상용 글꼴과 얼굴 인식 모델 확인 중…' -ForegroundColor Cyan
python tools/get_fonts.py
if ($LASTEXITCODE -ne 0) { Fail '글꼴을 내려받지 못했습니다. 인터넷 연결을 확인해 주세요.' }

Write-Host '렌더링 엔진 확인 중…' -ForegroundColor Cyan
npx -y hyperframes browser ensure
if ($LASTEXITCODE -ne 0) { Write-Host '렌더링 엔진을 미리 받지 못했습니다. 첫 렌더링 때 다시 받습니다.' -ForegroundColor Yellow }

$hasKey = (Test-Path .env) -and (Select-String -Path .env -Pattern '^GEMINI_API_KEY' -Quiet)
if (-not $hasKey -and -not $env:GEMINI_API_KEY) {
  $key = Read-Host "`nGemini API 키를 붙여 넣으세요(Google AI Studio에서 무료 발급, 나중에 넣으려면 Enter)"
  if ($key.Trim()) {
    # .env는 server.py가 UTF-8로 읽는다. PowerShell 5.1의 Add-Content 기본 인코딩을 쓰지 않는다.
    $sep = if ((Test-Path .env) -and (Get-Content .env -Raw) -and -not (Get-Content .env -Raw).EndsWith("`n")) { "`r`n" } else { '' }
    [IO.File]::AppendAllText((Join-Path $root '.env'), "${sep}GEMINI_API_KEY=$($key.Trim())`r`n", (New-Object Text.UTF8Encoding $false))
  }
}

$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'createMovie.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = Join-Path $root 'start.bat'
$s.WorkingDirectory = $root
$s.Save()
Write-Host '바탕화면에 createMovie 바로가기를 만들었습니다.' -ForegroundColor Green

if (Has 'nvidia-smi') {
  $go = $H3
  if (-not $go) {
    $ans = Read-Host "`nNVIDIA GPU가 있습니다. AI 영상 생성 도구도 설치할까요? 약 60GB를 내려받습니다. (y/N)"
    $go = $ans -eq 'y' -or $ans -eq 'Y'
  }
  if ($go) {
    python tools/setup_h3.py
    if ($LASTEXITCODE -ne 0) { Fail 'AI 영상 생성 도구를 설치하지 못했습니다. 다시 실행하면 이어서 진행합니다.' }
    Write-Host 'GPU 안전 설정을 적용합니다. 관리자 확인 창에서 예를 눌러 주세요.' -ForegroundColor Cyan
    powershell -NoProfile -ExecutionPolicy Bypass -File tools/gpu-safe.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File tools/gpu-safe-task.ps1
  }
} else {
  Write-Host "`nNVIDIA GPU가 없어 AI 영상 생성은 쓸 수 없습니다. 홍보 영상은 그대로 쓸 수 있습니다." -ForegroundColor Yellow
}

Write-Host "`n설치가 끝났습니다. 바탕화면의 createMovie로 실행하세요.`n" -ForegroundColor Green
