import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/errors";

describe("ApiError", () => {
  it("preserves structured backend failure metadata", () => {
    const error = new ApiError(409, { code: "REPLAY_LIMIT", message: "Replay limit reached", requestId: "req-1" });
    expect(error.status).toBe(409);
    expect(error.code).toBe("REPLAY_LIMIT");
    expect(error.requestId).toBe("req-1");
  });
});
