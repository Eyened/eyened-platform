import { Matrix } from "$lib/matrix";
import { describe, expect, it } from "vitest";
import { AffineRegistration } from "./affine";
import { CompositeRegistration } from "./composite";
import { glslPathBetween } from "./glslPathBetween";
import { ParabolicRegistration } from "./parabolic";
import type { Registration } from "./registration.svelte";
import type { RegistrationItem } from "./registrationItem";

const sizes: Record<string, [number, number]> = {
    a: [10, 20],
    b: [30, 40],
    c: [50, 60],
};

function registration(args: {
    path?: string[];
    items: Record<string, RegistrationItem>;
}): Registration {
    return {
        getPath: () => args.path,
        getRegistrationItem: (from: string, to: string) =>
            args.items[`${from}>${to}`],
    } as unknown as Registration;
}

describe("glslPathBetween", () => {
    it("returns an identity mapping for one image", () => {
        const glsl = glslPathBetween(
            registration({ items: {} }),
            "a",
            "a",
            () => undefined,
        );
        expect(glsl).toContain("return uv");
    });

    it("bakes a direct affine with both image sizes", () => {
        const glsl = glslPathBetween(
            registration({
                path: ["a", "b"],
                items: {
                    "a>b": new AffineRegistration("a", "b", Matrix.identity),
                },
            }),
            "a",
            "b",
            (id) => sizes[id],
        );
        expect(glsl).toContain("vec2 mapping(vec2 uv)");
        expect(glsl).toContain("10.0");
        expect(glsl).toContain("30.0");
    });

    it("bakes a parabolic hop", () => {
        const coeffs = [0, 0, 1, 0, 0.01, 0, 0];
        const glsl = glslPathBetween(
            registration({
                path: ["a", "b"],
                items: {
                    "a>b": new ParabolicRegistration("a", "b", coeffs, coeffs),
                },
            }),
            "a",
            "b",
            (id) => sizes[id],
        );
        expect(glsl).toContain("x * x");
    });

    it("bakes a path through an image that has no known size", () => {
        const coeffs = [0, 0, 0, 0, 0.01, 0, 0];
        const glsl = glslPathBetween(
            registration({
                path: ["a", "missing", "b"],
                items: {
                    "a>missing": new CompositeRegistration("a", "missing", [
                        new AffineRegistration("a", "missing", Matrix.identity),
                        new ParabolicRegistration(
                            "a",
                            "missing",
                            coeffs,
                            coeffs,
                        ),
                    ]),
                    "missing>b": new AffineRegistration(
                        "missing",
                        "b",
                        Matrix.identity,
                    ),
                },
            }),
            "a",
            "b",
            (id) => (id === "missing" ? undefined : sizes[id]),
        );
        expect(glsl).not.toBeNull();
        expect(glsl).toContain("x * x");
        expect(glsl).toContain("10.0");
        expect(glsl).toContain("30.0");
        expect(glsl).not.toContain("50.0");
    });

    it("returns null when the path or a size is missing", () => {
        expect(
            glslPathBetween(
                registration({ items: {} }),
                "a",
                "b",
                (id) => sizes[id],
            ),
        ).toBeNull();
        expect(
            glslPathBetween(
                registration({
                    path: ["a", "b"],
                    items: {
                        "a>b": new AffineRegistration(
                            "a",
                            "b",
                            Matrix.identity,
                        ),
                    },
                }),
                "a",
                "b",
                () => undefined,
            ),
        ).toBeNull();
    });
});
