import { describe, it, expect } from "vitest";
import {
    analyzePointSchema,
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
        severity: { type: "string", enum: ["mild", "severe"] as unknown as never },
    },
    required: ["x", "y"],
};

describe("isPointWidget", () => {
    it("detects x-eyened-widget point", () => {
        expect(
            isPointWidget({ "x-eyened-widget": "point", ...pointObject }),
        ).toBe(true);
        expect(isPointWidget(pointObject)).toBe(false);
    });
});

describe("analyzePointSchema", () => {
    it("ImageInstance single object → bare single", () => {
        const a = analyzePointSchema(
            { "x-eyened-widget": "point", ...pointObject },
            "ImageInstance",
        );
        expect(a).toMatchObject({
            cardinality: "single",
            storageMode: "bare",
            registrationMode: false,
        });
        expect(a!.enumExtras).toEqual([
            { key: "severity", values: ["mild", "severe"] },
        ]);
    });

    it("ImageInstance array → bare list", () => {
        const a = analyzePointSchema(
            {
                "x-eyened-widget": "point",
                type: "array",
                items: pointObject,
            },
            "ImageInstance",
        );
        expect(a).toMatchObject({ cardinality: "list", storageMode: "bare" });
    });

    it("Eye map of arrays → byPublicId list + registrationMode", () => {
        const a = analyzePointSchema(
            {
                "x-eyened-widget": "point",
                "x-eyened-point-mode": "registration",
                type: "object",
                additionalProperties: {
                    type: "array",
                    items: {
                        oneOf: [pointObject, { type: "null" }],
                    },
                },
            },
            "Eye",
        );
        expect(a).toMatchObject({
            cardinality: "list",
            storageMode: "byPublicId",
            registrationMode: true,
        });
    });

    it("returns null when widget present but shape is not point-like", () => {
        expect(
            analyzePointSchema(
                { "x-eyened-widget": "point", type: "string" },
                "ImageInstance",
            ),
        ).toBeNull();
    });
});

describe("get/setPointsForImage", () => {
    const bareSingle = analyzePointSchema(
        { "x-eyened-widget": "point", ...pointObject },
        "ImageInstance",
    )!;
    const mapList = analyzePointSchema(
        {
            "x-eyened-widget": "point",
            type: "object",
            additionalProperties: { type: "array", items: pointObject },
        },
        "Eye",
    )!;

    it("bare single round-trip", () => {
        const pts = [{ x: 1, y: 2 }];
        const value = setPointsForImage(undefined, "img-a", pts, bareSingle);
        expect(value).toEqual({ x: 1, y: 2 });
        expect(getPointsForImage(value, "img-a", bareSingle)).toEqual([
            { x: 1, y: 2 },
        ]);
        expect(setPointsForImage(value, "img-a", [], bareSingle)).toBeUndefined();
    });

    it("byPublicId list round-trip", () => {
        const value = setPointsForImage({}, "img-a", [{ x: 1, y: 2 }], mapList);
        expect(value).toEqual({ "img-a": [{ x: 1, y: 2 }] });
        expect(getPointsForImage(value, "img-a", mapList)).toEqual([
            { x: 1, y: 2 },
        ]);
        expect(getPointsForImage(value, "img-b", mapList)).toEqual([]);
    });
});
