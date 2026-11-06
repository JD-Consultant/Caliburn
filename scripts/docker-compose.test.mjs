import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));

// Parse the real Compose model without a daemon or repository credentials.
function resolveCompose(overrides = {}) {
  const temporary = mkdtempSync(path.join(os.tmpdir(), "caliburn-compose-"));
  try {
    const envFile = path.join(temporary, "compose.env");
    const appEnv = path.join(temporary, "app.env");
    writeFileSync(envFile, "");
    writeFileSync(appEnv, "OPENAI_API_KEY=synthetic-not-a-key\n");
    const env = Object.fromEntries(
      Object.entries(process.env).filter(
        ([key]) => !/^(CALIBURN_|COMPOSE_|REFERENCE_|OPENAI_)/iu.test(key),
      ),
    );
    Object.assign(env, {
      CALIBURN_POSTGRES_PASSWORD: "synthetic-password",
      CALIBURN_APP_ENV_FILE: appEnv,
      ...overrides,
    });
    return JSON.parse(
      execFileSync(
        "docker",
        [
          "compose",
          "--env-file",
          envFile,
          "-f",
          "compose.yaml",
          "config",
          "--format",
          "json",
        ],
        { cwd: root, env, encoding: "utf8", timeout: 30_000 },
      ),
    );
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}

test("the complete deployment has one application and both required databases", () => {
  const config = resolveCompose();
  assert.deepEqual(Object.keys(config.services).sort(), [
    "app",
    "postgres",
    "qdrant",
  ]);
  assert.equal(config.services.app.build.dockerfile, "Dockerfile");
  assert.equal(
    config.services.app.depends_on.postgres.condition,
    "service_healthy",
  );
  assert.equal(
    config.services.app.depends_on.qdrant.condition,
    "service_healthy",
  );
  assert.equal(
    config.services.app.environment.CALIBURN_REBUILD_REFERENCE_CONFIG,
    "/opt/caliburn/reference.json",
  );
  assert.equal(config.services.app.command ?? null, null);
});

test("only the app receives provider credentials and every published port is loopback-only", () => {
  const { services } = resolveCompose({ CALIBURN_APP_PORT: "18101" });
  assert.equal(services.app.environment.OPENAI_API_KEY, "synthetic-not-a-key");
  for (const name of ["postgres", "qdrant"])
    assert.equal(services[name].environment?.OPENAI_API_KEY, undefined);
  for (const service of Object.values(services)) {
    for (const port of service.ports) assert.equal(port.host_ip, "127.0.0.1");
  }
  assert.equal(services.app.ports[0].published, "18101");
});

test("an isolated project receives separate storage and app image without touching old volumes", () => {
  const normal = resolveCompose();
  const isolated = resolveCompose({
    COMPOSE_PROJECT_NAME: "caliburn-delivery-test",
  });
  assert.equal(normal.name, "caliburn-rebuild");
  assert.deepEqual(Object.keys(normal.volumes).sort(), [
    "postgres_data",
    "qdrant_data",
  ]);
  for (const name of Object.keys(normal.volumes)) {
    assert.notEqual(normal.volumes[name].name, isolated.volumes[name].name);
    assert.equal(normal.volumes[name].external, undefined);
  }
  assert.equal(normal.services.app.image, undefined);
  assert.equal(isolated.services.app.image, undefined);
});

test("model and config mounts are read-only and a misspelled config cannot create a directory", () => {
  const { app } = resolveCompose().services;
  assert.equal(app.read_only, true);
  assert.ok(app.volumes.every((volume) => volume.read_only));
  const config = app.volumes.find(
    (volume) => volume.target === "/opt/caliburn/reference.json",
  );
  assert.equal(config.bind?.create_host_path ?? false, false);
});
