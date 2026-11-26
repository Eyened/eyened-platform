import { describe, expect, it } from "vitest";
import { rightWidth } from "./rightWidth";

describe("rightWidth", () => {
    it("keeps a set width within 288 and 480 px", () => {
        expect(rightWidth(600, 2000)).toBe(480);
        expect(rightWidth(200, 2000)).toBe(288);
        expect(rightWidth(400, 2000)).toBe(400);
    });

    it("gives way so the viewport grid keeps 320 px, but never below 288", () => {
        // 700 px for grid and panel: the grid keeps 320, the panel gets 380.
        expect(rightWidth(480, 700)).toBe(380);
        // 500 px leaves the grid less than 320 once the panel is at 288.
        expect(rightWidth(480, 500)).toBe(288);
    });
});
