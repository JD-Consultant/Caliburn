param(
  [Parameter(Mandatory)][string]$Version,
  [Parameter(Mandatory)][string[]]$Plan,
  [string]$BaseUrl = 'http://127.0.0.1:8103',
  [string[]]$ExtraArgs = @()
)
# Run simulated interviews strictly one at a time. Plan items look like "warehouse:1"; existing outputs are skipped.
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$dir = 'S:\caliburn\.research-tmp\eval'
$items = $Plan | ForEach-Object { $_ -split ',' } | Where-Object { $_ }
foreach ($item in $items) {
  $persona, $n = $item.Trim() -split ':'
  $out = "$dir\$Version-$persona-$n.json"
  if (Test-Path $out) { Write-Host "skip $out (exists)"; continue }
  Write-Host "run $Version $persona #$n started $(Get-Date -Format HH:mm:ss)"
  $arguments = @('-B', 'scripts/simulate_interview.py', '--persona', $persona, '--base-url', $BaseUrl, '--key-file', 'S:/caliburn/apps/api/.env', '--output', $out, '--label', "$Version-$n") + $ExtraArgs
  Start-Process -FilePath 'S:\caliburn\apps\api\.venv-target\Scripts\python.exe' -ArgumentList $arguments `
    -WorkingDirectory 'S:\caliburn\apps\api' -Wait `
    -RedirectStandardOutput "$dir\$Version-$persona-$n.stdout.log" -RedirectStandardError "$dir\$Version-$persona-$n.stderr.log" -WindowStyle Hidden
  Write-Host "run $Version $persona #$n finished $(Get-Date -Format HH:mm:ss)"
}
Write-Host 'plan complete'
