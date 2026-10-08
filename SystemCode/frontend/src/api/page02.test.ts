import { afterEach, describe, expect, it, vi } from "vitest";
import { jobsApi } from "./jobs";
import { targetsApi } from "./targets";
import type { UserProfile } from "../types/api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("page 02 API contract", () => {
  it("requests ranking without a request body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ total_jobs: 0, passed_count: 0, returned_count: 0, rejected_by_rule: {}, results: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await jobsApi.rank();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/ranking", expect.objectContaining({ method: "POST" }));
    expect(fetchMock.mock.calls[0][1].body).toBeUndefined();
  });

  it("sends the saved profile when requesting match details", async () => {
    const profile = { resume_upload_id: null, resume: {}, constraints: {} } as UserProfile;
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await jobsApi.getMatchDetail(280, profile);

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/jobs/280/match-detail", expect.objectContaining({ method: "POST", body: JSON.stringify(profile) }));
  });

  it("adds and removes target jobs through the documented routes", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ job_id: 280 }, 201))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await targetsApi.add(280, 52.71);
    await targetsApi.remove(280);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/targets", expect.objectContaining({ method: "POST", body: JSON.stringify({ job_id: 280, match_score: 52.71 }) }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/targets/280", expect.objectContaining({ method: "DELETE" }));
  });
});
