import { describe, expect, it } from "vitest";
import { interviewErrorMessage } from "./messages";

const t = ((key: string) => key) as Parameters<typeof interviewErrorMessage>[1];

describe("interview device errors", () => {
  it("shows the translated hint instead of the browser's raw message", () => {
    const denied = new DOMException("Permission denied", "NotAllowedError");
    expect(interviewErrorMessage({ reason: denied, device: "microphone" }, t)).toBe("interview.error.microphone");
    expect(interviewErrorMessage({ reason: new DOMException("Requested device not found", "NotFoundError"), device: "microphone" }, t)).toBe("interview.error.noDevice");
  });
});
