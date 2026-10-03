param(
  [Parameter(Mandatory)][ValidateSet('start', 'stop', 'migrate')][string]$Action,
  [string]$Schema = 'b_compaction_20261002',
  [int]$Port = 8105
)
# T16 section 12 probe backend: isolated schema in the loopback _test database, own port, lowered B1/B2 pre-batch threshold.
$ErrorActionPreference = 'Stop'
$api = 'S:\caliburn\apps\api'
$py = "$api\.venv-target\Scripts\python.exe"
$launcher = 'S:\caliburn\.research-tmp\eval\tools\low_b_threshold_backend.py'
$log = "S:\caliburn\.research-tmp\b-probe-backend-$Port"

function Set-ProbeEnvironment {
  $env:PYTHONUTF8 = '1'
  $env:PYTHONPATH = $api
  $env:CALIBURN_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
  $env:CALIBURN_DATABASE_SCHEMA = $Schema
}

switch ($Action) {
  'migrate' {
    Set-ProbeEnvironment
    Push-Location $api
    try { & $py -m alembic -c alembic.ini upgrade head; if ($LASTEXITCODE -ne 0) { throw 'migration failed' } } finally { Pop-Location }
  }
  'stop' {
    $victims = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'low_b_threshold_backend\.py' -and $_.CommandLine -match "--port $Port(\s|$)" }
    foreach ($v in $victims) { Stop-Process -Id $v.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "stopped $(@($victims).Count) process(es) on port $Port"
  }
  'start' {
    Set-ProbeEnvironment
    Start-Process -FilePath $py -ArgumentList '-B', $launcher, '--key-file', 'S:/caliburn/apps/api/.env', '--port', "$Port" `
      -WorkingDirectory $api -WindowStyle Hidden -RedirectStandardOutput "$log.out.log" -RedirectStandardError "$log.err.log"
    for ($i = 0; $i -lt 60; $i++) {
      Start-Sleep -Seconds 1
      try { if ((Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/api/health").StatusCode -eq 200) { Write-Host "healthy on $Port (schema $Schema)"; return } } catch { }
    }
    throw "probe backend on $Port did not become healthy"
  }
}
