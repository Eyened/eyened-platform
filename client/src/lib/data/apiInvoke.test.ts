import { describe, expect, it, vi } from "vitest";
import { ApiError, isOutOfDeclaration } from "$lib/api/client";
import { authClient, type UserResponse } from "../../auth";
import { apiInvoke, apiInvokeAllowEmpty } from "./api";

// Separate from api.test.ts: that file mocks $lib/api/client wholesale,
// including the withAuthRetry these tests need the real version of.

const outOfDeclaration = {
    code: "image_outside_task_declaration",
    message: "Image abc is in a project this task does not declare.",
    image_projects: [17],
    declared_projects: [4, 9],
};

describe("ApiError", () => {
    it("carries a structured detail so a caller can branch on the code", () => {
        const err = new ApiError(409, "conflict", outOfDeclaration);
        expect(err.detail).toMatchObject({
            code: "image_outside_task_declaration",
        });
    });

    it("leaves detail undefined for the two-argument auth call sites", () => {
        const err = new ApiError(401, "Request failed: 401");
        expect(err.detail).toBeUndefined();
    });
});

describe("isOutOfDeclaration", () => {
    it("accepts a detail tagged with the declaration code", () => {
        const err = new ApiError(409, "conflict", outOfDeclaration);
        expect(isOutOfDeclaration(err)).toBe(true);
    });

    it("rejects a plain string detail", () => {
        const err = new ApiError(404, "Not found", "Not found");
        expect(isOutOfDeclaration(err)).toBe(false);
    });

    it("rejects an object detail carrying some other code", () => {
        const err = new ApiError(409, "conflict", { code: "something_else" });
        expect(isOutOfDeclaration(err)).toBe(false);
    });
});

describe("apiInvoke", () => {
    it("keeps the server's detail rather than discarding the body", async () => {
        // The API wraps every service error as {"detail": ...}, and
        // openapi-fetch hands that parsed body back as `res.error`.
        const call = vi.fn().mockResolvedValue({
            error: { detail: outOfDeclaration },
            response: new Response(null, { status: 409 }),
        });

        const thrown: unknown = await apiInvoke(call, "add image").then(
            () => null,
            (e) => e,
        );

        expect(thrown).toBeInstanceOf(ApiError);
        const err = thrown as ApiError;
        expect(err.status).toBe(409);
        expect(isOutOfDeclaration(err)).toBe(true);
        expect(err.detail).toMatchObject(outOfDeclaration);
        // The server's sentence beats the synthetic "Failed to add image: 409".
        expect(err.message).toBe(outOfDeclaration.message);
    });

    it("falls back to the synthetic message when the body carries none", async () => {
        const call = vi.fn().mockResolvedValue({
            error: { detail: undefined },
            response: new Response(null, { status: 500 }),
        });

        const thrown: unknown = await apiInvoke(call, "add image").then(
            () => null,
            (e) => e,
        );

        expect(thrown).toBeInstanceOf(ApiError);
        expect((thrown as ApiError).message).toBe("Failed to add image: 500");
    });

    it("uses a string detail as the message", async () => {
        const call = vi.fn().mockResolvedValue({
            error: { detail: "Subtask not found" },
            response: new Response(null, { status: 404 }),
        });

        const thrown: unknown = await apiInvoke(call, "add image").then(
            () => null,
            (e) => e,
        );

        expect((thrown as ApiError).message).toBe("Subtask not found");
        expect((thrown as ApiError).detail).toBe("Subtask not found");
    });

    it("keeps a validation body readable instead of stringifying it", async () => {
        // FastAPI's 422 detail is a list of field errors: an object, but with
        // no `message` of its own, so the synthetic sentence has to win.
        const detail = [
            {
                loc: ["body", "projects"],
                msg: "Field required",
                type: "missing",
            },
        ];
        const call = vi.fn().mockResolvedValue({
            error: { detail },
            response: new Response(null, { status: 422 }),
        });

        const thrown: unknown = await apiInvoke(call, "create task").then(
            () => null,
            (e) => e,
        );

        expect((thrown as ApiError).message).toBe("Failed to create task: 422");
        // The field errors survive for a caller that wants to render them.
        expect((thrown as ApiError).detail).toEqual(detail);
    });
});

describe("apiInvokeAllowEmpty", () => {
    it("returns the result even though openapi-fetch reported an error", async () => {
        // A 204 has no body to parse, which openapi-fetch reports as `error`.
        // Treating that as a failure is what this variant exists to avoid.
        const res = {
            error: {},
            response: new Response(null, { status: 204 }),
        };
        const call = vi.fn().mockResolvedValue(res);

        await expect(apiInvokeAllowEmpty(call)).resolves.toBe(res);
    });

    it("still refuses an unauthorized response, after one refresh and retry", async () => {
        // Allowing an empty body must not extend to letting a 403 through as
        // a successful result.
        const refresh = vi
            .spyOn(authClient, "refresh")
            .mockResolvedValue({} as UserResponse);
        const call = vi.fn().mockResolvedValue({
            error: { detail: "Not enough permissions." },
            response: new Response(null, { status: 403 }),
        });

        const thrown: unknown = await apiInvokeAllowEmpty(call).then(
            () => null,
            (e) => e,
        );

        expect(thrown).toBeInstanceOf(ApiError);
        expect((thrown as ApiError).status).toBe(403);
        expect((thrown as ApiError).message).toBe("Not enough permissions.");
        expect(refresh).toHaveBeenCalledTimes(1);
        expect(call).toHaveBeenCalledTimes(2);
    });

    it("names the status when an unauthorized body carries no detail", async () => {
        // An auth failure can surface as a status alone -- the HTTP layer
        // already retried and the body is gone. There is no operation name
        // here to build a sentence from, unlike apiInvoke.
        vi.spyOn(authClient, "refresh").mockResolvedValue({} as UserResponse);
        const call = vi.fn().mockResolvedValue({
            error: undefined,
            response: new Response(null, { status: 401 }),
        });

        const thrown: unknown = await apiInvokeAllowEmpty(call).then(
            () => null,
            (e) => e,
        );

        expect((thrown as ApiError).message).toBe("Request failed: 401");
        expect((thrown as ApiError).detail).toBeUndefined();
    });
});
