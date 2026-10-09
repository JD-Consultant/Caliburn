import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));

// Resolve the real Compose model without a daemon or any repository secrets.
function resolveCompose({
  rag = false,
  collection = "ocs_references_test",
  overrides = {},
} = {}) {
  const temporary = mkdtempSync(path.join(os.tmpdir(), "caliburn-compose-"));
  try {
    const keyFile = path.join(temporary, "key.env");
    const envFile = path.join(temporary, "compose.env");
    writeFileSync(keyFile, "OPENAI_API_KEY=synthetic-not-a-key\n");
    writeFileSync(envFile, "");
    const env = Object.fromEntries(
      Object.entries(process.env).filter(
        ([key]) => !/^(CALIBURN_|COMPOSE_|REFERENCE_)/iu.test(key),
      ),
    );
    Object.assign(env, {
      CALIBURN_POSTGRES_PASSWORD: "synthetic-database-password",
      CALIBURN_OPENAI_ENV_FILE: keyFile,
      CALIBURN_REFERENCE_COLLECTION: collection,
      ...overrides,
    });
    const args = [
      "compose",
      "--env-file",
      envFile,
      "-f",
      "compose.jd-app.yaml",
    ];
    if (rag) args.push("-f", "compose.jd-app.rag.yaml", "--profile", "rag");
    args.push("config", "--format", "json");
    return JSON.parse(
      execFileSync("docker", args, {
        cwd: root,
        env,
        encoding: "utf8",
        timeout: 30_000,
      }),
    );
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}

test("basic mode contains only the existing App and database", () => {
  const config = resolveCompose();
  assert.equal(config.name, "caliburn-jd-app");
  assert.deepEqual(Object.keys(config.services).sort(), ["app", "postgres"]);
  assert.equal(
    config.services.app.environment.CALIBURN_OCCUPATION_REFERENCE_URL,
    undefined,
  );
  assert.deepEqual(Object.keys(config.volumes), ["jd_postgres_data"]);
});

test("reference mode reuses the same App and database, with internal service addresses", () => {
  const basic = resolveCompose();
  const full = resolveCompose({ rag: true });
  assert.deepEqual(Object.keys(full.services).sort(), [
    "app",
    "embedder",
    "ocs-indexer",
    "postgres",
    "qdrant",
  ]);
  assert.equal(full.name, basic.name);
  assert.deepEqual(full.services.postgres, basic.services.postgres);
  assert.deepEqual(
    full.volumes.jd_postgres_data,
    basic.volumes.jd_postgres_data,
  );
  assert.equal(
    full.services.app.environment.CALIBURN_OCCUPATION_REFERENCE_URL,
    "http://ocs-indexer:8000",
  );
  assert.equal(
    full.services["ocs-indexer"].environment.QDRANT_URL,
    "http://qdrant:6333",
  );
  assert.equal(
    full.services["ocs-indexer"].environment.EMBEDDER_URL,
    "http://embedder:80",
  );
  assert.equal(
    full.services["ocs-indexer"].environment.REFERENCE_COLLECTION,
    "ocs_references_test",
  );
  assert.deepEqual(Object.keys(full.services.app.depends_on), ["postgres"]);
  assert.equal(
    full.services["ocs-indexer"].depends_on.qdrant.condition,
    "service_healthy",
  );
  assert.equal(
    full.services["ocs-indexer"].depends_on.embedder.condition,
    "service_healthy",
  );
});

test("reference services do not publish ports or receive the App credential", () => {
  const config = resolveCompose({ rag: true });
  assert.equal(
    config.services.app.environment.OPENAI_API_KEY,
    "synthetic-not-a-key",
  );
  for (const name of ["qdrant", "embedder", "ocs-indexer"]) {
    assert.equal(config.services[name].ports, undefined, name);
    assert.equal(
      config.services[name].environment?.OPENAI_API_KEY,
      undefined,
      name,
    );
  }
  const api = config.services["ocs-indexer"];
  assert.equal(api.read_only, true);
  assert.deepEqual(api.cap_drop, ["ALL"]);
  assert.equal(api.volumes, undefined);
  assert.ok(
    api.healthcheck.test.some((part) =>
      part.includes("http://127.0.0.1:8000/healthz"),
    ),
  );
  assert.equal(config.services.embedder.gpus[0].count, -1);
});

test("standalone RAG publishes only explicit loopback ports", () => {
  const config = JSON.parse(execFileSync("docker", [
    "compose", "--env-file", ".env.jd-app.example", "-f", "docker-compose.yml",
    "--profile", "rag", "config", "--format", "json",
  ], { cwd: root, encoding: "utf8", timeout: 30_000 }));
  const published = [];
  for (const name of ["qdrant", "embedder"]) {
    for (const port of config.services[name].ports) {
      assert.equal(port.host_ip, "127.0.0.1", `${name}:${port.published}`);
      published.push(port.published);
    }
  }
  assert.deepEqual(published.sort(), ["6333", "6334", "8082"]);
});

test("isolated RAG builds do not replace a shared model image tag", () => {
  const production = resolveCompose({ rag: true });
  const isolated = resolveCompose({
    rag: true,
    overrides: { COMPOSE_PROJECT_NAME: "caliburn-rag-isolation-test" },
  });
  assert.notEqual(production.name, isolated.name);
  assert.notEqual(
    production.volumes.qdrant_storage.name,
    isolated.volumes.qdrant_storage.name,
  );
  for (const config of [production, isolated]) {
    for (const name of ["app", "ocs-indexer", "embedder"]) {
      assert.equal(
        config.services[name].image,
        undefined,
        `${name} must use Compose's project-scoped build tag`,
      );
    }
  }
});

test("reference mode requires an explicitly chosen collection, without changing basic mode", () => {
  assert.doesNotThrow(() => resolveCompose({ collection: "" }));
  assert.throws(
    () => resolveCompose({ rag: true, collection: "" }),
    /CALIBURN_REFERENCE_COLLECTION/u,
  );
});

test("custom App ports remain loopback-only and RAG settings remain server-side", () => {
  const config = resolveCompose({
    rag: true,
    overrides: {
      CALIBURN_APP_PORT: "8105",
      CALIBURN_POSTGRES_PORT: "55445",
      CALIBURN_REFERENCE_CANDIDATE_LIMIT: "40",
    },
  });
  assert.equal(config.services.app.ports[0].host_ip, "127.0.0.1");
  assert.equal(config.services.app.ports[0].published, "8105");
  assert.equal(config.services.postgres.ports[0].published, "55445");
  assert.equal(
    config.services["ocs-indexer"].environment.REFERENCE_CANDIDATE_LIMIT,
    "40",
  );
  assert.equal(
    config.services.app.environment.REFERENCE_CANDIDATE_LIMIT,
    undefined,
  );
});
