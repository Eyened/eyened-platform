import { describe, expect, it } from "vitest";
import { apiErrorFromResponse } from "./client";

describe("apiErrorFromResponse", () => {
    // The raw-fetch auth calls in src/auth.ts are the only callers: they have a
    // Response in hand rather than an openapi-fetch result.
    it("reports the server's own sentence", async () => {
        const response = new Response(
            JSON.stringify({ detail: "OIDC state does not match." }),
            { status: 400 },
        );

        const err = await apiErrorFromResponse(response);

        expect(err.status).toBe(400);
        expect(err.message).toBe("OIDC state does not match.");
        expect(err.detail).toBe("OIDC state does not match.");
    });

    it("falls back to the status when the body is not a FastAPI error", async () => {
        // A gateway between the client and the app answers in its own shape,
        // and `detail` is absent. Without the fallback the message is
        // "undefined".
        const response = new Response(
            JSON.stringify({ error: "bad gateway" }),
            {
                status: 502,
            },
        );

        const err = await apiErrorFromResponse(response);

        expect(err.status).toBe(502);
        expect(err.message).toBe("Request failed: 502");
        expect(err.detail).toBeUndefined();
    });
});
