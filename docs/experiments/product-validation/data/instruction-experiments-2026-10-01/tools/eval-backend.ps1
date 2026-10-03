param(
  [Parameter(Mandatory)][ValidateSet('start', 'stop', 'restart', 'migrate')][string]$Action,
  [string]$Schema = 'eval_b',
  [int]$Port = 8103
)
# Isolated evaluation backend: own schema in the loopback _test database, own port. Never touches Demo 8100/5173.
$ErrorActionPreference = 'Stop'
$api = 'S:\caliburn\apps\api'
$py = "$api\.venv-target\Scripts\python.exe"
$log = "S:\caliburn\.research-tmp\eval-backend-$Port"

function Set-EvalEnvironment {
  $env:PYTHONUTF8 = '1'
  $env:CALIBURN_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
  $env:CALIBURN_DATABASE_SCHEMA = $Schema
  $env:CALIBURN_PDF_FONT_PATH = 'S:\caliburn\.research-tmp\delivery-clean-cae4f960-7b3e\fonts\NotoSansTC-VF.ttf'
  $env:CALIBURN_PDF_CHROMIUM_PATH = 'S:\caliburn\.research-tmp\chromium-153.0.8010.12\chrome-win64\chrome.exe'
}

function Stop-EvalBackend {
  $victims = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_backend\.py' -and $_.CommandLine -match "--port $Port(\s|$)" }
  foreach ($v in $victims) { Stop-Process -Id $v.ProcessId -Force -ErrorAction SilentlyContinue }
  Write-Host "stopped $(@($victims).Count) process(es) on port $Port"
}

function Invoke-Migration {
  Set-EvalEnvironment
  Push-Location $api
  try { & $py -m alembic -c alembic.ini upgrade head; if ($LASTEXITCODE -ne 0) { throw 'migration failed' } } finally { Pop-Location }
}

function Start-EvalBackend {
  Set-EvalEnvironment
  Start-Process -FilePath $py -ArgumentList '-B', 'scripts/run_backend.py', '--key-file', 'S:/caliburn/apps/api/.env', '--port', "$Port" `
    -WorkingDirectory $api -WindowStyle Hidden -RedirectStandardOutput "$log.out.log" -RedirectStandardError "$log.err.log"
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try { if ((Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/api/health").StatusCode -eq 200) { Write-Host "healthy on $Port (schema $Schema)"; return } } catch { }
  }
  throw "backend on $Port did not become healthy"
}

switch ($Action) {
  'migrate' { Invoke-Migration }
  'stop' { Stop-EvalBackend }
  'start' { Invoke-Migration; Start-EvalBackend }
  'restart' { Stop-EvalBackend; Start-Sleep -Seconds 2; Start-EvalBackend }
}
