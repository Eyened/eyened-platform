import { describe, expect, it } from "vitest";
import { Matrix } from "$lib/matrix";
import { AffineRegistration } from "./affine";
import { Registration } from "./registration.svelte";
import { glslPathBetween } from "./glslPathBetween";

function registrationWith(item: AffineRegistration) {
    const registration = new Registration();
    registration.importRegistrationItems([item]);
    registration.recomputePathsNow();
    return registration;
}

describe("glslPathBetween", () => {
    it("bakes a direct affine into mapping()", () => {
        const item = new AffineRegistration("fixed", "moving", Matrix.identity);
        const registration = registrationWith(item);
        const glsl = glslPathBetween(registration, "fixed", "moving", () => [10, 20]);
        expect(glsl).not.toBeNull();
        expect(glsl).toContain("vec2 mapping(vec2 uv)");
        expect(glsl).not.toContain("u_size_primary");
    });

    it("returns null when no path exists", () => {
        const registration = new Registration();
        registration.recomputePathsNow();
        expect(glslPathBetween(registration, "a", "b", () => [1, 1])).toBeNull();
    });

    it("returns null when a node has no size", () => {
        const item = new AffineRegistration("fixed", "moving", Matrix.identity);
        const registration = registrationWith(item);
        expect(
            glslPathBetween(registration, "fixed", "moving", (id) =>
                id === "fixed" ? [10, 10] : undefined,
            ),
        ).toBeNull();
    });
});
