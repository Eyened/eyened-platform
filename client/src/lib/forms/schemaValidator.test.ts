import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { validateSchema } from "./schemaValidator.svelte";

const formSchemasDir = resolve(
    import.meta.dirname,
    "../../../../orm/eyened_orm/form_schemas",
);

function loadSchema(name: string) {
    return JSON.parse(
        readFileSync(resolve(formSchemasDir, name), "utf8"),
    ) as unknown;
}

describe("validateSchema type checking", () => {
    it("rejects wrong primitive types", () => {
        const errors = validateSchema({ type: "number" }, "nope");
        expect(errors.some((e) => e.type === "type")).toBe(true);
    });

    it("accepts null only for type null", () => {
        expect(validateSchema({ type: "null" }, null)).toEqual([]);
        expect(
            validateSchema({ type: "null" }, { x: 1 }).some(
                (e) => e.type === "type",
            ),
        ).toBe(true);
    });

    it("accepts integers and rejects non-integers for type integer", () => {
        expect(validateSchema({ type: "integer" }, 3)).toEqual([]);
        expect(
            validateSchema({ type: "integer" }, 3.5).some(
                (e) => e.type === "type",
            ),
        ).toBe(true);
    });

    it("accepts union types including null", () => {
        expect(validateSchema({ type: ["number", "null"] }, 3)).toEqual([]);
        expect(validateSchema({ type: ["number", "null"] }, null)).toEqual([]);
        expect(
            validateSchema({ type: ["number", "null"] }, "x").some(
                (e) => e.type === "type",
            ),
        ).toBe(true);
    });

    it("makes oneOf discriminate object vs null", () => {
        const schema = {
            oneOf: [
                {
                    type: "object",
                    properties: {
                        x: { type: "number" },
                        y: { type: "number" },
                    },
                    required: ["x", "y"],
                    additionalProperties: false,
                },
                { type: "null" },
            ],
        };
        expect(validateSchema(schema, { x: 1, y: 2 })).toEqual([]);
        expect(validateSchema(schema, null)).toEqual([]);
        // Without type checks, {x,y} matched both arms (object + type:null).
        expect(
            validateSchema(schema, { x: 1, y: 2, z: 3 }).length,
        ).toBeGreaterThan(0);
    });
});

describe("validateSchema additionalProperties", () => {
    it("rejects undeclared keys when additionalProperties is false", () => {
        const schema = {
            type: "object",
            properties: { x: { type: "number" }, y: { type: "number" } },
            required: ["x", "y"],
            additionalProperties: false,
        };
        expect(validateSchema(schema, { x: 1, y: 2 })).toEqual([]);
        const errors = validateSchema(schema, { x: 1, y: 2, index: 0 });
        expect(errors.some((e) => e.type === "additionalProperties")).toBe(
            true,
        );
    });

    it("validates values under an additionalProperties schema", () => {
        const schema = {
            type: "object",
            additionalProperties: {
                type: "array",
                items: { type: "number" },
            },
        };
        expect(validateSchema(schema, { a: [1, 2] })).toEqual([]);
        expect(
            validateSchema(schema, { a: "nope" }).some(
                (e) => e.type === "type",
            ),
        ).toBe(true);
    });
});

describe("shipped pointset_registration schema", () => {
    const schema = loadSchema("pointset_registration.json");

    it("accepts plain and indexed landmarks", () => {
        expect(
            validateSchema(schema, {
                img1: [{ x: 1, y: 2 }],
                img2: [{ x: 3, y: 4, index: null }],
                img3: [{ x: 5, y: 6, index: 7 }, null],
            }),
        ).toEqual([]);
    });

    it("rejects undeclared point properties", () => {
        const errors = validateSchema(schema, {
            img1: [{ x: 1, y: 2, BOGUS: true }],
        });
        // Fails the object oneOf arm (additionalProperties:false) and the
        // null arm (type), so oneOf reports matched 0.
        expect(errors.length).toBeGreaterThan(0);
        expect(errors.some((e) => e.type === "oneOf")).toBe(true);
    });

    it("rejects a non-array under an image key", () => {
        const errors = validateSchema(schema, { img1: "not-an-array" });
        expect(errors.some((e) => e.type === "type")).toBe(true);
    });
});

describe("shipped etdrs_grid_coordinates schema", () => {
    const schema = loadSchema("etdrs_grid_coordinates.json");

    it("accepts fovea/disc without index", () => {
        expect(
            validateSchema(schema, {
                fovea: { x: 1, y: 2 },
                disc_edge: { x: 3, y: 4 },
            }),
        ).toEqual([]);
    });

    it("rejects stray index on landmarks", () => {
        const errors = validateSchema(schema, {
            fovea: { x: 1, y: 2, index: 0 },
        });
        expect(errors.some((e) => e.type === "additionalProperties")).toBe(
            true,
        );
    });
});
