import { afterEach, describe, expect, it, vi } from "vitest";
import { interviewApi } from "./interview";
import { targetsApi } from "./targets";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("page 04 API contract", () => {
  it("loads target jobs from the documented collection route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await targetsApi.list();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/targets", expect.objectContaining({}));
  });

  it("requests a ten-question interview set with the demo difficulty mix", async () => {
    const request = {
      count: 10,
      difficulty_mix: { easy: 4, medium: 4, hard: 2 },
      exclude_question_ids: [11, 12],
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ questions: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await interviewApi.sample(280, request);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/jobs/280/interview-questions/sample",
      expect.objectContaining({ method: "POST", body: JSON.stringify(request) }),
    );
  });

  it("uploads recorded audio as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ transcript: "Example answer" }));
    vi.stubGlobal("fetch", fetchMock);
    const audio = new Blob(["recording"], { type: "audio/webm" });

    await interviewApi.transcribe(280, 99, audio);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/jobs/280/interview-questions/99/transcription");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("audio")).toBeInstanceOf(File);
    expect(init.headers).toBeUndefined();
  });
});
