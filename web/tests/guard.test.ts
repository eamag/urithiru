import { describe, expect, it } from "bun:test";
import { overLaunchLimit, refuse } from "../src/lib/guard";

describe("guard authentication and rate limits", () => {
  it("refuses unauthorized launches in read-only deployment mode", () => {
    // When no URITHIRU_LAUNCH_TOKEN is set in test environment, deployment is read-only
    const req = new Request("http://localhost/api/runs", {
      method: "POST",
      headers: { authorization: "Bearer invalid-token" },
    });

    const result = refuse(req);
    expect(result).not.toBeNull();
    // Default without token is 503 (read-only)
    expect(result?.status).toBe(503);
    expect(result?.error).toContain("read-only");
  });

  it("handles launch rate limiting", () => {
    // Limit is 6 by default
    // First calls up to limit should be allowed (if quota remains)
    let hitLimit = false;
    for (let i = 0; i < 10; i++) {
      const res = overLaunchLimit();
      if (res !== null) {
        hitLimit = true;
        expect(res.status).toBe(429);
        expect(res.error).toContain("Launch limit reached");
        break;
      }
    }
    expect(hitLimit).toBe(true);
  });
});
