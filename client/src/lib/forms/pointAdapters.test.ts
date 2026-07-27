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
        const analysis = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            ...pointObject,
        })!;
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

    it("round-trips byImage list", () => {
        let value: unknown = {};
        const analysis = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            additionalProperties: { type: "array", items: pointObject },
        })!;
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
            slotLabels: ["Fovea", "Disc edge"],
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
        expect(adapter.slotLabels).toEqual(["Fovea", "Disc edge"]);
        expect(adapter.analysis.cardinality).toBe("list");
        expect(adapter.analysis.sparse).toBe(true);
        expect(adapter.analysis.addressing).toBe("bare");
    });

    it("defaults slotLabels to slot keys", () => {
        const adapter = createMultiFieldAdapter({
            slots: ["fovea", "disc_edge"],
            getPublicId: () => "img-a",
            getFormData: () => ({}),
            setFormData: () => {},
        });
        expect(adapter.slotLabels).toEqual(["fovea", "disc_edge"]);
    });
});
