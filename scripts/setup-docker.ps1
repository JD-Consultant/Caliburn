# First setup, or an update after the App has been safely stopped and backed up.
# Requires only Docker Desktop and Windows PowerShell 5.1 / PowerShell 7.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-Docker {
    param([string[]]$Arguments, [string]$Failure)

    # Compose config can contain credentials. Capture output without printing it;
    # a failed command reports its stage and exit code, never its raw output.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & docker @Arguments 2>$null
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($code -ne 0) {
        $diagnosticArguments = $Arguments
        $configIndex = [Array]::IndexOf($Arguments, 'config')
        if ($configIndex -ge 0) {
            # config --format json prints every resolved secret. Recommend only
            # validation when the user needs the underlying Compose diagnostic.
            $diagnosticArguments = $Arguments[0..$configIndex] + @('--quiet')
        }
        $diagnostic = ($diagnosticArguments | ForEach-Object { "'" + $_.Replace("'", "''") + "'" }) -join ' '
        throw "$Failure (Docker exit code $code).`nFor details, run in PowerShell: docker $diagnostic"
    }
    return ($output | Out-String).Trim()
}

$repository = Split-Path -Parent $PSScriptRoot
$environmentFile = Join-Path $repository '.env'
$compose = @('compose', '-f', (Join-Path $repository 'compose.jd-app.yaml'))
$locationPushed = $false
try {
    Push-Location -LiteralPath $repository
    $locationPushed = $true
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker is not installed or is not on PATH. Install and start Docker Desktop first.'
    }

    Write-Host 'Checking Docker Desktop and Compose...'
    $engine = Invoke-Docker -Arguments @('info', '--format', '{{.OSType}}') -Failure 'Docker is not available; start Docker Desktop'
    if ($engine -ne 'linux') { throw 'Docker must use Linux containers.' }
    $composeVersion = Invoke-Docker -Arguments @('compose', 'version', '--short') -Failure 'Docker Compose is not available'
    if ($composeVersion -notmatch '^v?(\d+\.\d+\.\d+)') { throw 'Cannot determine Docker Compose version; version 2.24.0 or newer is required.' }
    if ([version]$Matches[1] -lt [version]'2.24.0') { throw 'Docker Compose 2.24.0 or newer is required. Update Docker Desktop.' }

    $needsEnvironment = -not (Test-Path -LiteralPath $environmentFile)
    if ($env:CALIBURN_POSTGRES_PASSWORD) {
        throw 'Unset the shell CALIBURN_POSTGRES_PASSWORD before setup and save the intended password in .env. A shell override would replace the saved password.'
    }
    if ($env:COMPOSE_ENV_FILES -or $env:COMPOSE_DISABLE_ENV_FILE) {
        throw 'Unset COMPOSE_ENV_FILES and COMPOSE_DISABLE_ENV_FILE before setup. This entrypoint uses the repository .env for setup and daily startup.'
    }

    $newPassword = $null
    $previousPassword = $env:CALIBURN_POSTGRES_PASSWORD
    try {
        if ($needsEnvironment) {
            $bytes = New-Object byte[] 32
            $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
            try { $random.GetBytes($bytes) } finally { $random.Dispose() }
            $newPassword = ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
            # Resolve project, volume and port through Compose itself. The temporary
            # password permits resolution before .env exists; it is never printed.
            $env:CALIBURN_POSTGRES_PASSWORD = $newPassword
        }
        $configText = Invoke-Docker -Arguments ($compose + @('config', '--format', 'json')) -Failure 'Compose configuration is invalid; check .env and the optional API key file'
        try { $config = $configText | ConvertFrom-Json }
        catch { throw 'Compose configuration could not be read as JSON.' }
    }
    finally {
        $env:CALIBURN_POSTGRES_PASSWORD = $previousPassword
    }

    $password = [string]$config.services.postgres.environment.POSTGRES_PASSWORD
    if ($password -notmatch '^[A-Za-z0-9_-]+$') {
        throw 'CALIBURN_POSTGRES_PASSWORD must be a nonempty URL-safe password: letters, digits, hyphens and underscores. Existing .env was not changed.'
    }
    $port = @($config.services.app.ports | Where-Object { $_.target -eq 8100 })[0].published
    $volumeName = $config.volumes.jd_postgres_data.name
    if ($needsEnvironment) {
        $volumes = Invoke-Docker -Arguments @('volume', 'ls', '--format', '{{.Name}}') -Failure 'Could not check existing database volumes'
        if (($volumes -split '\r?\n') -contains $volumeName) {
            throw 'The database volume already exists but .env is missing. Restore its original .env before continuing; setup will not generate a replacement password.'
        }
    }
    $runningApp = Invoke-Docker -Arguments @('ps', '--filter', "label=com.docker.compose.project=$($config.name)", '--filter', 'label=com.docker.compose.service=app', '--format', '{{.ID}}') -Failure 'Could not check whether the App is running'
    if ($runningApp) {
        throw 'The App is running. Follow the update guide to finish active work, stop the App safely and back up the database before rerunning setup.'
    }

    if ($needsEnvironment) {
        $template = [System.IO.File]::ReadAllText((Join-Path $repository '.env.jd-app.example'))
        $contents = $template -replace '(?m)^CALIBURN_POSTGRES_PASSWORD=\r?$', "CALIBURN_POSTGRES_PASSWORD=$newPassword"
        # CreateNew prevents overwriting settings created by another process.
        $file = [System.IO.File]::Open($environmentFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try {
            $data = (New-Object System.Text.UTF8Encoding $false).GetBytes($contents)
            $file.Write($data, 0, $data.Length)
        }
        finally { $file.Dispose() }
        Write-Host 'Created .env with a database password. Keep this file with your database backups.'
    }
    else { Write-Host 'Keeping the existing .env unchanged.' }

    Write-Host '[1/4] Building the App image. The first build downloads dependencies and may take several minutes...'
    $null = Invoke-Docker -Arguments ($compose + @('build', 'app')) -Failure 'App image build failed; retry the build after checking Docker and network access'
    Write-Host '[2/4] Starting PostgreSQL and waiting for it to be healthy...'
    $null = Invoke-Docker -Arguments ($compose + @('up', '-d', '--wait', 'postgres')) -Failure 'PostgreSQL startup failed; inspect the postgres service logs'
    Write-Host '[3/4] Applying database migrations...'
    $null = Invoke-Docker -Arguments ($compose + @('run', '--rm', 'app', 'alembic', '-c', '/opt/caliburn/alembic.ini', 'upgrade', 'head')) -Failure 'Database migration failed; the App was not started'
    Write-Host '[4/4] Starting the App and waiting for its health check...'
    $null = Invoke-Docker -Arguments ($compose + @('up', '-d', '--wait', 'app')) -Failure 'App startup failed; inspect the app service logs'
    Write-Host "Ready: http://127.0.0.1:$port"
    Write-Host 'AI requires an OPENAI_API_KEY in the optional apps/api/.env key file. See docs/operations/getting-started.md for setup and checks.'
}
catch {
    [Console]::Error.WriteLine("Setup failed: $($_.Exception.Message)")
    exit 1
}
finally {
    if ($locationPushed) { Pop-Location }
}
