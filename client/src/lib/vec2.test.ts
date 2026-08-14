import { describe, it, expect } from "vitest";
import { Vec2, vec2 } from "./vec2";

describe("Vec2", () => {
    it("computes length for a 3-4-5 triangle", () => {
        expect(new Vec2(3, 4).length()).toBe(5);
    });

    it("adds and subtracts componentwise", () => {
        const a = new Vec2(1, 2);
        const b = new Vec2(3, 5);
        expect(a.add(b)).toEqual(new Vec2(4, 7));
        expect(b.sub(a)).toEqual(new Vec2(2, 3));
    });

    it("scales with mul", () => {
        expect(new Vec2(2, -3).mul(2)).toEqual(new Vec2(4, -6));
    });

    it("computes dot and cross products", () => {
        const a = new Vec2(1, 2);
        const b = new Vec2(3, 4);
        expect(a.dot(b)).toBe(11); // 1*3 + 2*4
        expect(a.cross(b)).toBe(-2); // 1*4 - 2*3
    });

    it("returns the angle via atan2", () => {
        expect(new Vec2(0, 1).angle()).toBeCloseTo(Math.PI / 2);
        expect(new Vec2(1, 0).angle()).toBe(0);
    });
});

describe("vec2 factory", () => {
    it("wraps a point into a Vec2", () => {
        const v = vec2({ x: 7, y: 8 });
        expect(v).toBeInstanceOf(Vec2);
        expect([v.x, v.y]).toEqual([7, 8]);
    });
});
