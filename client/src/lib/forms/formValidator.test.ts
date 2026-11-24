import { describe, expect, it } from "vitest";
import {
    checkForm,
    validateSchema,
    type ValidationError,
} from "./formValidator";
import type { JSONSchema } from "./schemaType";

const S2020 = "https://json-schema.org/draft/2020-12/schema";
const S07 = "http://json-schema.org/draft-07/schema#";

/** The keywords that failed at one path. */
const at = (errors: ValidationError[], path: string) =>
    errors.filter((e) => e.path === path).map((e) => e.type);

describe("validateSchema", () => {
    it("checks each schema by the draft its $schema names, ignoring _order and x-eyened keys", () => {
        // A tuple is `prefixItems` in 2020-12 and `items: [...]` in draft-07; the wrong build misses or rejects it.
        const modern = {
            $schema: S2020,
            type: "object",
            _order: ["pair"],
            properties: {
                pair: { type: "array", prefixItems: [{ type: "string" }] },
            },
        } as unknown as JSONSchema;
        const old = {
            $schema: S07,
            type: "object",
            _order: ["pair"],
            properties: {
                pair: {
                    type: "array",
                    items: [{ type: "string" }],
                    "x-eyened-widget": "other",
                },
            },
        } as unknown as JSONSchema;
        expect(at(validateSchema(modern, { pair: [1] }), "/pair/0")).toEqual([
            "type",
        ]);
        expect(at(validateSchema(old, { pair: [1] }), "/pair/0")).toEqual([
            "type",
        ]);
        expect(validateSchema(old, { pair: ["a"] })).toEqual([]);
    });

    it("flags issue 348's range, pattern and item-count cases", () => {
        const schema = {
            $schema: S2020,
            type: "object",
            properties: {
                age: { type: "integer", minimum: 0, maximum: 120 },
                code: { type: "string", pattern: "^[A-Z]{2}$" },
                tags: { type: "array", items: { type: "string" }, maxItems: 2 },
            },
        } as JSONSchema;
        const errors = validateSchema(schema, {
            age: 130,
            code: "abc",
            tags: ["a", "b", "c"],
        });
        expect(at(errors, "/age")).toEqual(["maximum"]);
        expect(at(errors, "/code")).toEqual(["pattern"]);
        expect(at(errors, "/tags")).toEqual(["maxItems"]);
        expect(at(validateSchema(schema, { age: -1 }), "/age")).toEqual([
            "minimum",
        ]);
    });

    it("follows a ref to the root and an escaped pointer without throwing", () => {
        const schema = {
            $schema: S07,
            type: "object",
            properties: {
                child: { $ref: "#" },
                "a/b": { $ref: "#/definitions/a~1b" },
            },
            definitions: { "a/b": { type: "string" } },
        } as JSONSchema;
        expect(validateSchema(schema, { child: { child: {} } })).toEqual([]);
        expect(at(validateSchema(schema, { "a/b": 3 }), "/a~1b")).toEqual([
            "type",
        ]);
    });

    it("points a missing answer at the question", () => {
        const schema = {
            type: "object",
            required: ["grade"],
            properties: { grade: { enum: ["A"] } },
        } as JSONSchema;
        expect(validateSchema(schema, {}).map((e) => [e.path, e.type])).toEqual(
            [["/grade", "required"]],
        );
    });
});

describe("checkForm", () => {
    it("reports one form-level error for a schema that won't compile, without throwing", () => {
        const broken = {
            $schema: S07,
            type: "object",
            properties: { x: { type: "int" } },
        } as unknown as JSONSchema;
        const check = checkForm(broken, { x: 1 });
        expect(check.schemaError).toBe(true);
        expect(check.errors).toHaveLength(1);
    });

    it("rules out a question an allOf condition turns off, from the current answers", () => {
        const schema = {
            $schema: S2020,
            type: "object",
            properties: {
                seen: { enum: ["Yes", "No"] },
                size: { type: "number" },
            },
            allOf: [
                {
                    if: {
                        properties: { seen: { const: "No" } },
                        required: ["seen"],
                    },
                    then: { properties: { size: false } },
                },
            ],
        } as unknown as JSONSchema;
        expect([...checkForm(schema, { seen: "No" }).ruledOut]).toEqual([
            "/size",
        ]);
        expect([...checkForm(schema, { seen: "Yes" }).ruledOut]).toEqual([]);
        expect(
            at(checkForm(schema, { seen: "No", size: 3 }).errors, "/size"),
        ).toEqual(["false schema"]);
    });

    it("names a question a condition makes required, only while the condition holds", () => {
        const schema = {
            $schema: S2020,
            type: "object",
            properties: {
                grade: { enum: ["absent", "present"] },
                severity: { enum: ["mild", "severe"] },
            },
            allOf: [
                {
                    if: {
                        properties: { grade: { const: "present" } },
                        required: ["grade"],
                    },
                    then: { required: ["severity"] },
                },
            ],
        } as unknown as JSONSchema;
        expect([
            ...checkForm(schema, { grade: "present" }).requiredNow,
        ]).toEqual(["/severity"]);
        expect([...checkForm(schema, { grade: "absent" }).requiredNow]).toEqual(
            [],
        );
    });
});
