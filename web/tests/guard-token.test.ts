import { describe, expect, it } from "bun:test";

/**
 * The guard reads its token once, at module load, so a deployment cannot be unlocked or
 * relocked while it is serving. These tests import it fresh with the variable set, which
 * is the only way to exercise the configured path.
 */
async function loadGuard(token: string, limit?: string) {
  process.env.URITHIRU_LAUNCH_TOKEN = token;
  if (limit) process.env.URITHIRU_LAUNCH_LIMIT = limit;
  // A query string defeats the module cache, so each test gets its own token and counter.
  return await import(`../src/lib/guard.ts?token=${encodeURIComponent(token)}&limit=${limit ?? ""}`);
}

function post(authorization?: string): Request {
  return new Request("http://localhost/api/runs", {
    method: "POST",
    headers: authorization ? { authorization } : {},
  });
}

describe("a deployment with a launch token", () => {
  it("reports itself as able to launch", async () => {
    const guard = await loadGuard("s3cret-operator-token");
    expect(guard.launchEnabled).toBe(true);
  });

  it("accepts exactly the configured token", async () => {
    const guard = await loadGuard("s3cret-operator-token");
    expect(guard.refuse(post("Bearer s3cret-operator-token"))).toBeNull();
  });

  it("rejects a wrong, absent, truncated or unprefixed token with 401", async () => {
    const guard = await loadGuard("s3cret-operator-token");
    for (const header of [
      undefined,
      "Bearer wrong-token-entirely",
      "Bearer s3cret-operator-toke",
      "Bearer s3cret-operator-tokenX",
      "s3cret-operator-token",
      "Basic s3cret-operator-token",
      "Bearer ",
    ]) {
      const refusal = guard.refuse(post(header));
      expect(refusal).not.toBeNull();
      expect(refusal?.status).toBe(401);
    }
  });

  it("stops accepting launches once the hourly limit is spent", async () => {
    const guard = await loadGuard("another-token", "3");
    expect(guard.overLaunchLimit()).toBeNull();
    expect(guard.overLaunchLimit()).toBeNull();
    expect(guard.overLaunchLimit()).toBeNull();
    const refusal = guard.overLaunchLimit();
    expect(refusal?.status).toBe(429);
    expect(refusal?.error).toContain("3 runs per hour");
  });
});
