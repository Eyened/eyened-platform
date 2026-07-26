import { describe, it, expect } from "vitest";
import {
    cycleEnumExtra,
    deletePointAt,
    movePointAt,
    placePoint,
} from "./pointMutations";

describe("placePoint", () => {
    it("single replaces", () => {
        expect(
            placePoint([{ x: 1, y: 1 }], { x: 9, y: 9 }, "single", false),
        ).toEqual([{ x: 9, y: 9 }]);
        expect(placePoint([], { x: 9, y: 9 }, "single", false)).toEqual([
            { x: 9, y: 9 },
        ]);
    });

    it("stores optional volume index", () => {
        expect(
            placePoint([], { x: 9, y: 9 }, "single", false, { index: 12 }),
        ).toEqual([{ x: 9, y: 9, index: 12 }]);
    });

    it("stores null index for enface", () => {
        expect(
            placePoint([], { x: 9, y: 9 }, "single", false, { index: null }),
        ).toEqual([{ x: 9, y: 9, index: null }]);
    });

    it("omits index when option not provided", () => {
        expect(placePoint([], { x: 9, y: 9 }, "single", false)).toEqual([
            { x: 9, y: 9 },
        ]);
    });

    it("list appends", () => {
        expect(
            placePoint([{ x: 1, y: 1 }], { x: 2, y: 2 }, "list", false),
        ).toEqual([
            { x: 1, y: 1 },
            { x: 2, y: 2 },
        ]);
    });

    it("registration fills first null slot", () => {
        const pts = [{ x: 1, y: 1 }, null, { x: 3, y: 3 }] as const;
        expect(placePoint([...pts], { x: 2, y: 2 }, "list", true)).toEqual([
            { x: 1, y: 1 },
            { x: 2, y: 2 },
            { x: 3, y: 3 },
        ]);
    });
});

describe("deletePointAt", () => {
    it("splices in normal list mode", () => {
        expect(
            deletePointAt([{ x: 1, y: 1 }, { x: 2, y: 2 }], 0, false),
        ).toEqual([{ x: 2, y: 2 }]);
    });

    it("nulls mid-list in registration mode; splices last", () => {
        expect(
            deletePointAt([{ x: 1, y: 1 }, { x: 2, y: 2 }], 0, true),
        ).toEqual([null, { x: 2, y: 2 }]);
        expect(
            deletePointAt([{ x: 1, y: 1 }, { x: 2, y: 2 }], 1, true),
        ).toEqual([{ x: 1, y: 1 }]);
    });
});

describe("movePointAt / cycleEnumExtra", () => {
    it("moves and preserves null index", () => {
        expect(
            movePointAt([{ x: 1, y: 1, index: null }], 0, { x: 5, y: 6 }),
        ).toEqual([{ x: 5, y: 6, index: null }]);
    });

    it("moves and preserves index", () => {
        expect(
            movePointAt([{ x: 1, y: 1, index: 3 }], 0, { x: 5, y: 6 }),
        ).toEqual([{ x: 5, y: 6, index: 3 }]);
    });

    it("moves and cycles", () => {
        expect(movePointAt([{ x: 1, y: 1 }], 0, { x: 5, y: 6 })).toEqual([
            { x: 5, y: 6 },
        ]);
        expect(cycleEnumExtra({ x: 1, y: 1 }, "severity", ["a", "b"])).toEqual({
            x: 1,
            y: 1,
            severity: "a",
        });
        expect(
            cycleEnumExtra({ x: 1, y: 1, severity: "a" }, "severity", ["a", "b"]),
        ).toEqual({ x: 1, y: 1, severity: "b" });
    });
});
