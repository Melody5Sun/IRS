import { afterEach, describe, expect, it, vi } from "vitest";
import { profileApi } from "./profile";
import { resumesApi } from "./resumes";
import type { UserProfile } from "../types/api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("page 01 API contract", () => {
  it("loads profile options and resume history from the documented routes", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ target_role_categories: { Software: ["Backend Developer"] }, target_industries: ["Internet"] }))
      .mockResolvedValueOnce(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await profileApi.getOptions();
    await resumesApi.getHistory();

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/profile/options", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/resumes/history", expect.any(Object));
  });

  it("saves the complete profile with resume_upload_id", async () => {
    const profile: UserProfile = {
      resume_upload_id: 8,
      resume: {
        name: "Alex", email: "alex@example.com", phone: "123",
        experiences: [], projects: [], research: [], skills: ["Python"],
        skill_groups: [], educations: [], certificates: [], languages: ["English"],
        awards: [], additional_info: [],
      },
      constraints: {
        target_roles: ["Backend Developer"], target_industries: ["Internet"],
        work_modes: ["hybrid"], target_employment_types: ["internship"], notes: "",
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ...profile, updated_at: "2026-10-08T10:00:00Z" }));
    vi.stubGlobal("fetch", fetchMock);

    await profileApi.save(profile);

    const [, request] = fetchMock.mock.calls[0];
    expect(request.method).toBe("PUT");
    expect(JSON.parse(request.body)).toEqual(profile);
  });

  it("uploads a PDF as FormData without forcing a JSON content type", async () => {
    const parsed = {
      id: 3, filename: "resume.pdf", name: "Alex", uploaded_at: "2026-10-08T10:00:00Z",
      resume: { name: "Alex", email: null, phone: null, experiences: [], projects: [], research: [], skills: [], skill_groups: [], educations: [], certificates: [], languages: [], awards: [], additional_info: [], about: null },
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(parsed));
    vi.stubGlobal("fetch", fetchMock);

    await resumesApi.parsePdf(new File(["pdf"], "resume.pdf", { type: "application/pdf" }));

    const [, request] = fetchMock.mock.calls[0];
    expect(request.method).toBe("POST");
    expect(request.body).toBeInstanceOf(FormData);
    expect(request.headers).toBeUndefined();
  });
});
