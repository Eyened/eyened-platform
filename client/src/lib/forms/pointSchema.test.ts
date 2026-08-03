import { describe, it, expect } from "vitest";
import {
    analyzePointSchema,
    canPlaceOnViewer,
    getPointsForImage,
    isPointWidget,
    setPointsForImage,
} from "./pointSchema";
import type { JSONSchema } from "./schemaType";

const pointObject: JSONSchema = {
    type: "object",
    properties: {
        x: { type: "number" },
        y: { type: "number" },
        severity: {
            type: "string",
            enum: ["mild", "severe"] as unknown as never,
        },
    },
    required: ["x", "y"],
};

describe("isPointWidget", () => {
    it("detects keypoint marker", () => {
        expect(
            isPointWidget({ "x-eyened-widget": "keypoint", ...pointObject }),
        ).toBe(true);
        expect(isPointWidget(pointObject)).toBe(false);
    });
});

describe("analyzePointSchema", () => {
    it("bare single object", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            ...pointObject,
        });
        expect(a).toMatchObject({
            cardinality: "single",
            addressing: "bare",
            sparse: false,
            coordinateSpace: "enface2d",
        });
        expect(a!.enumExtras).toEqual([
            { key: "severity", values: ["mild", "severe"] },
        ]);
    });

    it("bare list", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "array",
            items: pointObject,
        });
        expect(a).toMatchObject({
            cardinality: "list",
            addressing: "bare",
            sparse: false,
            coordinateSpace: "enface2d",
        });
    });

    it("byImage map of arrays → list, not sparse", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            additionalProperties: {
                type: "array",
                items: pointObject,
            },
        });
        expect(a).toMatchObject({
            cardinality: "list",
            addressing: "byImage",
            sparse: false,
            coordinateSpace: "enface2d",
        });
    });

    it("byImage map of nullable arrays → sparse", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            additionalProperties: {
                type: "array",
                items: {
                    oneOf: [pointObject, { type: "null" }],
                },
            },
        });
        expect(a).toMatchObject({
            cardinality: "list",
            addressing: "byImage",
            sparse: true,
            coordinateSpace: "enface2d",
        });
    });

    it("accepts anyOf for nullable items", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            additionalProperties: {
                type: "array",
                items: {
                    anyOf: [pointObject, { type: "null" }],
                },
            },
        });
        expect(a).toMatchObject({ sparse: true, addressing: "byImage" });
    });

    it("byImage single point per image", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            additionalProperties: pointObject,
        });
        expect(a).toMatchObject({
            cardinality: "single",
            addressing: "byImage",
            sparse: false,
            coordinateSpace: "enface2d",
        });
    });

    it("declaring index number|null → oct (both)", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            properties: {
                x: { type: "number" },
                y: { type: "number" },
                index: { type: ["number", "null"] },
            },
            required: ["x", "y"],
        });
        expect(a).toMatchObject({
            cardinality: "single",
            addressing: "bare",
            coordinateSpace: "oct",
        });
    });

    it("numeric index without null → volume-only (even if optional)", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            properties: {
                x: { type: "number" },
                y: { type: "number" },
                index: { type: "number" },
            },
            required: ["x", "y"],
        });
        expect(a).toMatchObject({
            cardinality: "single",
            addressing: "bare",
            coordinateSpace: "volume",
        });
    });

    it("required numeric index → volume-only", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            properties: {
                x: { type: "number" },
                y: { type: "number" },
                index: { type: "number" },
            },
            required: ["x", "y", "index"],
        });
        expect(a).toMatchObject({ coordinateSpace: "volume" });
    });

    it("registration-shaped sparse list with index → oct", () => {
        const a = analyzePointSchema({
            "x-eyened-widget": "keypoint",
            type: "object",
            additionalProperties: {
                type: "array",
                items: {
                    oneOf: [
                        {
                            type: "object",
                            properties: {
                                x: { type: "number" },
                                y: { type: "number" },
                                index: { type: ["number", "null"] },
                            },
                            required: ["x", "y"],
                        },
                        { type: "null" },
                    ],
                },
            },
        });
        expect(a).toMatchObject({
            cardinality: "list",
            addressing: "byImage",
            sparse: true,
            coordinateSpace: "oct",
        });
    });

    it("returns null when widget present but shape is not point-like", () => {
        expect(
            analyzePointSchema({
                "x-eyened-widget": "keypoint",
                type: "string",
            }),
        ).toBeNull();
    });
});

describe("canPlaceOnViewer", () => {
    it("rejects OCT volumes for enface2d", () => {
        const r = canPlaceOnViewer("enface2d", { is3D: true });
        expect(r.ok).toBe(false);
        if (!r.ok) expect(r.message).toMatch(/2D-only/);
    });

    it("allows 2D / enface for enface2d", () => {
        expect(canPlaceOnViewer("enface2d", { is3D: false }).ok).toBe(true);
    });

    it("allows OCT volumes and 2D for oct (both)", () => {
        expect(canPlaceOnViewer("oct", { is3D: true }).ok).toBe(true);
        expect(canPlaceOnViewer("oct", { is3D: false }).ok).toBe(true);
    });

    it("rejects non-volumes for volume-only", () => {
        const r = canPlaceOnViewer("volume", { is3D: false });
        expect(r.ok).toBe(false);
        if (!r.ok) expect(r.message).toMatch(/OCT B-scan volume/);
    });

    it("allows OCT volumes for volume-only", () => {
        expect(canPlaceOnViewer("volume", { is3D: true }).ok).toBe(true);
    });
});

describe("get/setPointsForImage", () => {
    const bareSingle = analyzePointSchema({
        "x-eyened-widget": "keypoint",
        ...pointObject,
    })!;
    const mapList = analyzePointSchema({
        "x-eyened-widget": "keypoint",
        type: "object",
        additionalProperties: { type: "array", items: pointObject },
    })!;

    it("bare single round-trip", () => {
        const pts = [{ x: 1, y: 2 }];
        const value = setPointsForImage(undefined, "img-a", pts, bareSingle);
        expect(value).toEqual({ x: 1, y: 2 });
        expect(getPointsForImage(value, "img-a", bareSingle)).toEqual([
            { x: 1, y: 2 },
        ]);
        expect(
            setPointsForImage(value, "img-a", [], bareSingle),
        ).toBeUndefined();
    });

    it("byImage list round-trip", () => {
        const value = setPointsForImage({}, "img-a", [{ x: 1, y: 2 }], mapList);
        expect(value).toEqual({ "img-a": [{ x: 1, y: 2 }] });
        expect(getPointsForImage(value, "img-a", mapList)).toEqual([
            { x: 1, y: 2 },
        ]);
        expect(getPointsForImage(value, "img-b", mapList)).toEqual([]);
    });
});
