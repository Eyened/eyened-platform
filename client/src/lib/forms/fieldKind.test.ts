import { describe, expect, it } from "vitest";
import { fieldKind, orderedKeys, titleAt } from "./fieldKind";
import type { JSONSchema } from "./schemaType";

const kind = (schema: unknown, root: unknown = {}) =>
    fieldKind(schema as JSONSchema, root as JSONSchema);

describe("fieldKind", () => {
    it("draws 5 options as radios and 6 as a dropdown", () => {
        expect(kind({ enum: ["a", "b", "c", "d", "e"] })).toBe("radios");
        expect(kind({ enum: ["a", "b", "c", "d", "e", "f"] })).toBe("dropdown");
    });

    it("draws a nullable string as text and a boolean as yes/no", () => {
        expect(kind({ type: ["string", "null"] })).toBe("text");
        expect(kind({ type: "boolean" })).toBe("yesno");
    });

    it("draws picking several of 5 as checkboxes and of 6 as a multi-select", () => {
        const of = (n: number) => ({
            type: "array",
            items: { enum: ["a", "b", "c", "d", "e", "f"].slice(0, n) },
        });
        expect(kind(of(5))).toBe("checkboxes");
        expect(kind(of(6))).toBe("multiselect");
    });

    it("draws a list of objects as a repeating group, through $ref, and a number list as a value list", () => {
        const root = {
            $defs: {
                naevus: {
                    type: "object",
                    properties: { size: { type: "number" } },
                },
            },
        };
        expect(
            kind({ type: "array", items: { $ref: "#/$defs/naevus" } }, root),
        ).toBe("group-list");
        expect(kind({ type: "array", items: { type: "integer" } })).toBe(
            "value-list",
        );
    });

    it("calls type int unsupported and a keypoint widget a point", () => {
        expect(kind({ type: "int" })).toBe("unsupported");
        expect(
            kind({
                "x-eyened-widget": "keypoint",
                type: "object",
                properties: { x: { type: "number" }, y: { type: "number" } },
            }),
        ).toBe("point");
    });
});

describe("orderedKeys", () => {
    it("follows _order and puts keys it doesn't list last", () => {
        expect(
            orderedKeys({
                _order: ["c", "a"],
                properties: { a: {}, b: {}, c: {} },
            } as JSONSchema),
        ).toEqual(["c", "a", "b"]);
    });
});

describe("titleAt", () => {
    it("names a question inside a repeating group by its own label", () => {
        const root = {
            type: "object",
            properties: {
                naevi: {
                    type: "array",
                    description: "Naevi",
                    items: {
                        type: "object",
                        description: "Naevus",
                        properties: {
                            size: { type: "number", description: "Size" },
                        },
                    },
                },
            },
        } as JSONSchema;
        expect(titleAt(root, "/naevi/1/size")).toBe("Size");
        expect(titleAt(root, "/naevi/1")).toBe("Naevus 2");
    });
});
