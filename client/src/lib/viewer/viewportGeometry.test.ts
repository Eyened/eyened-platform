import { Matrix } from "$lib/matrix";
import { describe, expect, it } from "vitest";
import { boxToPaint, clipBox, keepViewOnResize } from "./viewportGeometry";

describe("keepViewOnResize", () => {
    it("keeps the image point at the centre", () => {
        const view = Matrix.from_translate_scale(-40, 25, 2.5, 2.5);
        const next = keepViewOnResize(
            view,
            { width: 400, height: 300 },
            { width: 640, height: 200 },
        );
        const centreBefore = view.inverse.apply({ x: 200, y: 150 });
        const centreAfter = next.inverse.apply({ x: 320, y: 100 });
        expect(centreAfter.x).toBeCloseTo(centreBefore.x);
        expect(centreAfter.y).toBeCloseTo(centreBefore.y);
    });
});

describe("clipBox", () => {
    it("intersects a viewer box with the grid and is null when nothing is left", () => {
        const grid = { left: 0, top: 0, width: 300, height: 100 };
        expect(
            clipBox({ left: -50, top: 0, width: 132, height: 92 }, grid),
        ).toEqual({
            left: 0,
            top: 0,
            width: 82,
            height: 92,
        });
        expect(
            clipBox({ left: -200, top: 0, width: 132, height: 92 }, grid),
        ).toBeNull();
    });
});

describe("boxToPaint", () => {
    const size = { width: 200, height: 100 };
    const current = { left: 0, top: 0, width: 200, height: 100 };

    it("adopts a box that only moved", () => {
        const moved = { left: 50, top: 10, width: 200, height: 100 };
        expect(boxToPaint(moved, current, size)).toEqual(moved);
    });

    it("keeps the current box when the size changed", () => {
        const resized = { left: 50, top: 10, width: 300, height: 100 };
        expect(boxToPaint(resized, current, size)).toEqual(current);
    });
});
