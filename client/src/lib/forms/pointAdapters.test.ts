import { describe, it, expect } from "vitest";
import { createFieldAdapter, createMultiFieldAdapter } from "./pointAdapters";
import { analyzePointSchema } from "./pointSchema";
import type { JSONSchema } from "./schemaType";

const pointObject: JSONSchema = {
    type: "object",
    properties: {
        x: { type: "number" },
        y: { type: "number" },
    },
    required: ["x", "y"],
};

describe("createFieldAdapter", () => {
    it("round-trips bare single via get/setPoints", () => {
        let value: unknown = undefined;
        const analysis = analyzePointSchema(
            { "x-eyened-widget": "point", ...pointObject },
            "ImageInstance",
        )!;
        const adapter = createFieldAdapter({
            analysis,
            getPublicId: () => "img-a",
            getFieldValue: () => value,
            setFieldValue: (next) => {
                value = next;
            },
        });
        adapter.setPoints([{ x: 1, y: 2 }]);
        expect(value).toEqual({ x: 1, y: 2 });
        expect(adapter.getPoints()).toEqual([{ x: 1, y: 2 }]);
        adapter.setPoints([]);
        expect(value).toBeUndefined();
    });

    it("round-trips byPublicId list", () => {
        let value: unknown = {};
        const analysis = analyzePointSchema(
            {
                "x-eyened-widget": "point",
                type: "object",
                additionalProperties: { type: "array", items: pointObject },
            },
            "Eye",
        )!;
        const adapter = createFieldAdapter({
            analysis,
            getPublicId: () => "img-a",
            getFieldValue: () => value,
            setFieldValue: (next) => {
                value = next;
            },
        });
        adapter.setPoints([{ x: 1, y: 2 }]);
        expect(value).toEqual({ "img-a": [{ x: 1, y: 2 }] });
        expect(adapter.getPoints()).toEqual([{ x: 1, y: 2 }]);
    });
});

describe("createMultiFieldAdapter", () => {
    it("maps slots to form_data fields", () => {
        let form_data: Record<string, unknown> = {
            fovea: { x: 10, y: 20 },
        };
        const adapter = createMultiFieldAdapter({
            slots: ["fovea", "disc_edge"],
            slotLabels: ["fovea", "disc"],
            getPublicId: () => "img-a",
            getFormData: () => form_data,
            setFormData: (next) => {
                form_data = next;
            },
        });
        expect(adapter.getPoints()).toEqual([{ x: 10, y: 20 }, null]);
        adapter.setPoints([
            { x: 10, y: 20 },
            { x: 30, y: 40 },
        ]);
        expect(form_data).toEqual({
            fovea: { x: 10, y: 20 },
            disc_edge: { x: 30, y: 40 },
        });
        adapter.setPoints([{ x: 10, y: 20 }, null]);
        expect(form_data).toEqual({ fovea: { x: 10, y: 20 } });
        expect(adapter.slotLabels).toEqual(["fovea", "disc"]);
        expect(adapter.analysis.cardinality).toBe("list");
        expect(adapter.analysis.registrationMode).toBe(true);
    });
});
