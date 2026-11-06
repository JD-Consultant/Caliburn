/** Exercise the installed container against an explicitly selected synthetic deployment. */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

const base = process.env.CALIBURN_SMOKE_URL;
if (
  !base ||
  !["127.0.0.1", "localhost", "[::1]"].includes(new URL(base).hostname)
) {
  throw new Error(
    "Set CALIBURN_SMOKE_URL to the isolated loopback deployment.",
  );
}
const request = (route, options = {}) =>
  fetch(new URL(route, base), {
    signal: AbortSignal.timeout(30_000),
    ...options,
  });

const health = await request("/api/health");
assert.equal(health.status, 200);
assert.equal((await health.json()).status, "ok");
for (const route of ["/", "/workspaces/synthetic-browser-route"]) {
  const response = await request(route, { headers: { Accept: "text/html" } });
  assert.equal(response.status, 200, route);
  assert.match(response.headers.get("content-type"), /text\/html/u);
}
const bareApi = await request("/api", { headers: { Accept: "text/html" } });
assert.equal(bareApi.status, 404);
assert.match(bareApi.headers.get("content-type"), /application\/json/u);
assert.equal((await request("/api/nonexistent")).status, 404);
assert.equal((await request("/assets/missing.js")).status, 404);
const contract = await request("/api/openapi.json");
assert.equal(contract.status, 200);
assert.ok((await contract.json()).paths["/occupation-references:search"]);

const created = await request("/api/workspaces", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ interviewee_name: `Delivery smoke ${randomUUID()}` }),
});
assert.equal(created.status, 201);
const { workspace_id: id } = await created.json();
assert.ok(id);
try {
  const workspace = await request(`/api/workspaces/${id}`);
  assert.equal(workspace.status, 200);
  const jd = await request(`/api/workspaces/${id}/job-description`);
  assert.equal(jd.status, 200);
  const document = await jd.json();
  const pdf = await request(
    `/api/workspaces/${id}/job-descriptions/${document.job_description_id}/export.pdf`,
  );
  assert.equal(pdf.status, 200);
  assert.match(pdf.headers.get("content-type"), /application\/pdf/u);
  assert.equal(
    Buffer.from(await pdf.arrayBuffer())
      .subarray(0, 5)
      .toString(),
    "%PDF-",
  );
} finally {
  assert.equal(
    (await request(`/api/workspaces/${id}`, { method: "DELETE" })).status,
    204,
  );
}
assert.equal((await request(`/api/workspaces/${id}`)).status, 404);
console.log(
  "Container smoke passed: health, SPA, API isolation, public reference routes, workspace persistence and PDF.",
);
