import { describe, expect, it } from "vitest";
import { ApiError } from "$lib/api/client";
import { json, stubFetch } from "../vitest-fetch";
import { authClient } from "./auth";

describe("authClient.login", () => {
    it.each([401, 500])(
        "rejects with an ApiError of status %i",
        async (status) => {
            stubFetch({
                "POST /api/auth/login": () =>
                    json({ detail: "refused" }, status),
            });

            const err = await authClient
                .login("ada", "pw")
                .catch((e: unknown) => e);

            expect(err).toBeInstanceOf(ApiError);
            expect((err as ApiError).status).toBe(status);
        },
    );
});
