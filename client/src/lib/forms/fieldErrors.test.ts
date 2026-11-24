import { describe, expect, it } from "vitest";
import { fieldErrors } from "./fieldErrors";
import type { ValidationError } from "./formValidator";

const err = (
    path: string,
    type: string,
    params: Record<string, unknown> = {},
    schemaPath = "#",
): ValidationError => ({
    path,
    type,
    params,
    schemaPath,
    message: `ajv: ${type}`,
});

describe("fieldErrors", () => {
    it("asks for a missing answer on that question", () => {
        expect(fieldErrors([err("/grade", "required")], {}).get("/grade")).toBe(
            "Answer this question.",
        );
    });

    it("asks for a whole number when a decimal reached an integer question", () => {
        const messages = fieldErrors(
            [err("/count", "type", { type: "integer" })],
            {
                count: 2.7,
            },
        );
        expect(messages.get("/count")).toBe("Enter a whole number.");
    });

    it("tells a ruled-out answer to be cleared", () => {
        expect(
            fieldErrors([err("/size", "false schema")], { size: 3 }).get(
                "/size",
            ),
        ).toBe("This question doesn't apply any more. Clear the answer.");
    });

    it("puts a failed oneOf with no question-level error on its section, and drops branch errors", () => {
        const messages = fieldErrors(
            [
                err(
                    "/eye/b",
                    "required",
                    {},
                    "#/properties/eye/oneOf/1/required",
                ),
                err("/eye", "oneOf", {}, "#/properties/eye/oneOf"),
            ],
            { eye: { a: 1 } },
        );
        expect([...messages]).toEqual([
            ["/eye", "These answers don't fit together."],
        ]);
    });

    it("shows ajv's words for a failed oneOf on a single question", () => {
        expect(fieldErrors([err("/n", "oneOf")], { n: "x" }).get("/n")).toBe(
            "ajv: oneOf",
        );
    });
});
