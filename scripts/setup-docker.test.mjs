import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, copyFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const shells = process.platform === "win32" ? ["powershell", "pwsh"] : ["pwsh"];
const availableShells = shells.filter((shell) => spawnSync(shell, ["-NoProfile", "-Command", "exit 0"]).status === 0);
assert.ok(availableShells.length, "Setup tests require Windows PowerShell or PowerShell 7.");

// Replace Docker's external boundary only; execute the actual setup script and
// filesystem changes in a fresh repository fixture with no host credentials.
function runSetup(shell, scenario = {}, existingEnv) {
  const directory = mkdtempSync(path.join(os.tmpdir(), "caliburn-setup-"));
  mkdirSync(path.join(directory, "scripts"));
  for (const file of ["compose.jd-app.yaml", ".env.jd-app.example", "scripts/setup-docker.ps1"]) {
    if (existsSync(path.join(root, file))) copyFileSync(path.join(root, file), path.join(directory, file));
  }
  if (existingEnv !== undefined) writeFileSync(path.join(directory, ".env"), existingEnv);
  writeFileSync(path.join(directory, "scenario.json"), JSON.stringify({
    fail: null, engine: null, version: null, invalidConfig: false,
    volumeExists: false, appRunning: false, warning: false, ...scenario,
  }));
  writeFileSync(path.join(directory, "runner.ps1"), String.raw`
$ErrorActionPreference = 'Stop'
$scenario = Get-Content -Raw (Join-Path $PSScriptRoot 'scenario.json') | ConvertFrom-Json
function global:docker {
  $arguments = @($args | ForEach-Object { [string]$_ })
  @{ arguments = $arguments; directory = (Get-Location).Path } | ConvertTo-Json -Compress | Add-Content (Join-Path $PSScriptRoot 'calls.jsonl')
  $global:LASTEXITCODE = 0
  $command = $arguments -join ' '
  if ($scenario.warning) { Write-Error 'A nonfatal Docker diagnostic.' -ErrorAction Continue }
  if ($scenario.fail -and $command -match $scenario.fail) {
    $global:LASTEXITCODE = 17
    Write-Output 'diagnostic contains synthetic-secret-do-not-print'
    return
  }
  if ($arguments[0] -eq 'info') {
    if ($scenario.engine) { $scenario.engine } else { 'linux' }
    return
  }
  if ($command -eq 'compose version --short') {
    if ($scenario.version) { $scenario.version } else { '2.24.0' }
    return
  }
  if ($command -match ' config --format json$') {
    if ($scenario.invalidConfig) { 'not-json'; return }
    $password = $env:CALIBURN_POSTGRES_PASSWORD
    if (-not $password -and (Test-Path (Join-Path $PSScriptRoot '.env'))) {
      $line = Get-Content (Join-Path $PSScriptRoot '.env') | Where-Object { $_ -match '^CALIBURN_POSTGRES_PASSWORD=' } | Select-Object -First 1
      $password = $line -replace '^CALIBURN_POSTGRES_PASSWORD=', ''
    }
    @{ name = 'fixture-project'; volumes = @{ jd_postgres_data = @{ name = 'fixture-project_jd_postgres_data' } }; services = @{
      postgres = @{ environment = @{ POSTGRES_PASSWORD = $password } }
      app = @{ environment = @{ OPENAI_API_KEY = 'synthetic-secret-do-not-print' }; ports = @(@{ target = 8100; published = '18765'; host_ip = '127.0.0.1' }) }
    } } | ConvertTo-Json -Depth 10 -Compress
    return
  }
  if ($arguments[0] -eq 'volume' -and $arguments[1] -eq 'ls') {
    if ($scenario.volumeExists) { 'fixture-project_jd_postgres_data' }
    return
  }
  if ($arguments[0] -eq 'ps') {
    if ($scenario.appRunning) { 'running-app-id' }
    return
  }
  if ($command -match ' (build app|up -d --wait postgres|run --rm app alembic -c /opt/caliburn/alembic.ini upgrade head|up -d --wait app)$') { return }
  throw "Unexpected Docker invocation: $command"
}
& (Join-Path $PSScriptRoot 'scripts/setup-docker.ps1')
exit $LASTEXITCODE
`);
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !/^(CALIBURN_|COMPOSE_|OPENAI_)/iu.test(key)));
  env.OPENAI_API_KEY = "host-key-must-not-be-copied";
  if (scenario.passwordOverride) env.CALIBURN_POSTGRES_PASSWORD = scenario.passwordOverride;
  Object.assign(env, scenario.envOverrides);
  try {
    const execution = spawnSync(shell, ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path.join(directory, "runner.ps1")], {
      cwd: os.tmpdir(), env, encoding: "utf8", timeout: 30_000, windowsHide: true,
    });
    assert.ifError(execution.error);
    const callsFile = path.join(directory, "calls.jsonl");
    const calls = existsSync(callsFile) ? readFileSync(callsFile, "utf8").replace(/^\uFEFF/u, "").trim().split(/\r?\n/u).map((line) => JSON.parse(line)) : [];
    return {
      status: execution.status,
      output: execution.stdout + execution.stderr,
      env: existsSync(path.join(directory, ".env")) ? readFileSync(path.join(directory, ".env"), "utf8") : undefined,
      calls,
      directory,
      operations: calls.map((call) => call.arguments.join(" ")).filter((command) => / (build|up|run) /u.test(command)),
    };
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

const existingEnv = "# Preserve my settings\r\nCALIBURN_POSTGRES_PASSWORD=existing-db-secret\r\nCALIBURN_APP_PORT=18765\r\nCUSTOM_SETTING=leave-me-alone\r\n";
const operationSuffixes = ["build app", "up -d --wait postgres", "run --rm app alembic -c /opt/caliburn/alembic.ini upgrade head", "up -d --wait app"];

for (const shell of availableShells) {
  test(`${shell}: first setup saves a random password and starts only after migration`, () => {
    const result = runSetup(shell);
    assert.equal(result.status, 0, result.output);
    assert.match(result.env, /^CALIBURN_POSTGRES_PASSWORD=[a-f0-9]{64}$/mu);
    assert.equal(result.operations.length, 4);
    result.operations.forEach((command, index) => assert.ok(command.endsWith(operationSuffixes[index]), command));
    assert.ok(result.calls.every((call) => path.resolve(call.directory) === path.resolve(result.directory)));
    assert.match(result.output, /http:\/\/127\.0\.0\.1:18765/u);
    assert.doesNotMatch(result.output, /synthetic-secret|host-key/u);
    assert.doesNotMatch(result.env, /host-key|OPENAI_API_KEY=/u);
    const password = result.env.match(/^CALIBURN_POSTGRES_PASSWORD=(.+)$/mu)[1];
    assert.ok(!result.output.includes(password), "Database password must not be printed.");
  });

  test(`${shell}: rerunning setup preserves the entire existing environment file`, () => {
    const result = runSetup(shell, { volumeExists: true }, existingEnv);
    assert.equal(result.status, 0, result.output);
    assert.equal(result.env, existingEnv);
    assert.equal(result.operations.length, 4);
    assert.doesNotMatch(result.output, /existing-db-secret|synthetic-secret/u);
  });

  test(`${shell}: shell password overrides cannot initialize a database with a different saved password`, () => {
    const result = runSetup(shell, { passwordOverride: "transient-password" }, existingEnv);
    assert.notEqual(result.status, 0);
    assert.equal(result.env, existingEnv);
    assert.deepEqual(result.operations, []);
    assert.match(result.output, /CALIBURN_POSTGRES_PASSWORD/iu);
    assert.doesNotMatch(result.output, /existing-db-secret|transient-password/u);
  });

  test(`${shell}: successful Docker diagnostics on stderr do not corrupt machine output`, () => {
    const result = runSetup(shell, { warning: true }, existingEnv);
    assert.equal(result.status, 0, result.output);
    assert.equal(result.operations.length, 4);
  });

  test(`${shell}: failed builds report an exact diagnostic command without credentials`, () => {
    const result = runSetup(shell, { fail: " build app$" }, existingEnv);
    assert.notEqual(result.status, 0);
    assert.match(result.output, /docker 'compose' '-f' '.+' 'build' 'app'/u);
    assert.doesNotMatch(result.output, /existing-db-secret|synthetic-secret/u);
  });

  test(`${shell}: failed config diagnostics recommend validation without exposing resolved secrets`, () => {
    const result = runSetup(shell, { fail: " config " }, existingEnv);
    assert.notEqual(result.status, 0);
    assert.match(result.output, /'config' '--quiet'/u);
    assert.doesNotMatch(result.output, /--format|synthetic-secret/u);
  });

  for (const [variable, value] of [["COMPOSE_ENV_FILES", "other.env"], ["COMPOSE_DISABLE_ENV_FILE", "1"]]) {
    test(`${shell}: config discovery override ${variable} cannot bypass saved settings`, () => {
      const result = runSetup(shell, { envOverrides: { [variable]: value } });
      assert.notEqual(result.status, 0);
      assert.equal(result.env, undefined);
      assert.deepEqual(result.operations, []);
      assert.ok(result.output.includes(variable), result.output);
    });
  }

  for (const [name, scenario, error] of [
    ["Docker daemon unavailable", { fail: "^info " }, /Docker.*(available|running|failed)/iu],
    ["Windows container engine", { engine: "windows" }, /Linux/iu],
    ["unsupported Compose", { version: "2.23.3" }, /2\.24/iu],
    ["invalid Compose config", { fail: " config " }, /config/iu],
    ["malformed Compose output", { invalidConfig: true }, /config/iu],
    ["existing database without its config", { volumeExists: true }, /\.env/iu],
    ["running app", { appRunning: true }, /(stop|running)/iu],
    ["transient password override", { passwordOverride: "transient-password" }, /CALIBURN_POSTGRES_PASSWORD/iu],
  ]) {
    test(`${shell}: ${name} fails before creating config or changing services`, () => {
      const result = runSetup(shell, scenario);
      assert.notEqual(result.status, 0);
      assert.equal(result.env, undefined);
      assert.deepEqual(result.operations, []);
      assert.match(result.output, error);
      assert.doesNotMatch(result.output, /synthetic-secret|transient-password/u);
    });
  }

  test(`${shell}: an invalid saved password is preserved and rejected before build`, () => {
    const contents = "CALIBURN_POSTGRES_PASSWORD=bad/password\n";
    const result = runSetup(shell, {}, contents);
    assert.notEqual(result.status, 0);
    assert.equal(result.env, contents);
    assert.deepEqual(result.operations, []);
    assert.match(result.output, /URL-safe/iu);
    assert.doesNotMatch(result.output, /bad\/password/u);
  });

  for (const [index, operation] of operationSuffixes.entries()) {
    test(`${shell}: failure during ${operation} prevents every later operation`, () => {
      const result = runSetup(shell, { fail: operation.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&") + "$" }, existingEnv);
      assert.notEqual(result.status, 0);
      assert.equal(result.env, existingEnv);
      assert.equal(result.operations.length, index + 1);
      assert.doesNotMatch(result.output, /http:\/\/127\.0\.0\.1:18765|synthetic-secret/u);
    });
  }
}
