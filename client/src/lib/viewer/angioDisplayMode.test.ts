import { describe, expect, it } from "vitest";
import { ANGIO_MODE_UNIFORM, angioModeUniform } from "./angioDisplayMode";

describe("angioModeUniform", () => {
    it("maps modes to shader ints", () => {
        expect(angioModeUniform("structural")).toBe(0);
        expect(angioModeUniform("flow")).toBe(1);
        expect(angioModeUniform("overlay")).toBe(2);
        expect(ANGIO_MODE_UNIFORM.overlay).toBe(2);
    });
});
