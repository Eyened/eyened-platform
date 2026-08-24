import { describe, expect, it, vi } from "vitest";
import { ApiError, isOutOfDeclaration } from "$lib/api/client";
import { apiInvoke } from "./api";

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
});
