import React from "react";
import { it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, cleanup } from "@testing-library/react";
import { DocumentList } from "./DocumentList";
import { api } from "../jd/api";
import { requestRecoveryCache } from "../jd/requestRecoveryCache";
afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); });
it.each(["slow", "failed"])("reads existing create recovery independently of %s list GET", async (mode) => {
  requestRecoveryCache(localStorage).writeCreate({ title: "原建立", request_key: "old-key" });
  vi.spyOn(api, "documents").mockImplementation(() => mode === "slow" ? new Promise(() => {}) : Promise.reject(Error("offline")));
  const create = vi.spyOn(api, "create").mockRejectedValue(Error("lost reply"));
  render(<DocumentList />);
  await waitFor(() => expect(screen.getByText("確認上次建立結果：原建立")).toBeTruthy());
  expect((screen.getByRole("button", { name: "建立文件" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.submit(screen.getByLabelText("文件名稱").closest("form")!);
  expect(create).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "依原記錄再次確認" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith({ title: "原建立", request_key: "old-key" }));
});
it("unreadable create cache blocks handler even when list GET succeeds", async () => {
  vi.spyOn(Storage.prototype, "key").mockImplementation(() => { throw Error("storage denied"); });
  localStorage.setItem("unrelated", "value");
  vi.spyOn(api, "documents").mockResolvedValue([]);
  const create = vi.spyOn(api, "create");
  render(<DocumentList />);
  await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  fireEvent.submit(screen.getByLabelText("文件名稱").closest("form")!);
  expect(create).not.toHaveBeenCalled();
});
it("does not present an API failure as an empty catalog", async () => {
  vi.spyOn(api, "documents").mockRejectedValueOnce(Error("offline"));
  render(<DocumentList />);
  await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  expect(screen.queryByText("尚未建立文件")).toBeNull();
  vi.restoreAllMocks();
});
