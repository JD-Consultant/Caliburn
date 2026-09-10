import { it, expect } from "vitest";
import { assertContract } from "../src/validate.js";
import { fixture, profile } from "./helpers.js";
it("SSOT validates transport and separates model refs from saved ids", () => {
  expect(() =>
    assertContract("JdPlateValidateValueRequest", { profile, value: fixture }),
  ).not.toThrow();
  expect(() =>
    assertContract("JdResolvedEditCommand", {
      type: "set_properties",
      target_id: "task-1",
      set: { knowledge_refs: ["ref"] },
    }),
  ).toThrow();
  expect(() =>
    assertContract("JdNewElement", {
      type: "p",
      id: "model-id",
      children: [{ text: "x" }],
    }),
  ).toThrow();
});
