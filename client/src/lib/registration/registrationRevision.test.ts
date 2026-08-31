import { describe, it, expect } from "vitest";
import { Matrix } from "$lib/matrix";
import { AffineRegistration } from "./affine";
import { Registration } from "./registration.svelte";

describe("Registration.revision", () => {
    it("starts at zero", () => {
        expect(new Registration().revision).toBe(0);
    });

    it("bumps when registration items are imported", () => {
        const registration = new Registration();
        registration.importRegistrationItems(
            [new AffineRegistration("fundus", "oct1_proj", Matrix.identity)],
            false,
        );
        expect(registration.revision).toBe(1);
    });

    it("bumps again for the debounced path recomputation", async () => {
        const registration = new Registration();
        registration.importRegistrationItems(
            [new AffineRegistration("fundus", "oct1_proj", Matrix.identity)],
            false,
        );
        const afterImport = registration.revision;

        await Promise.resolve();

        expect(registration.revision).toBeGreaterThan(afterImport);
    });

    it("bumps on an explicit synchronous recomputation", () => {
        const registration = new Registration();
        const before = registration.revision;
        registration.recomputePathsNow();
        expect(registration.revision).toBe(before + 1);
    });

    it("clears mapped cursor cache when paths recompute", () => {
        const registration = new Registration();
        registration.importRegistrationItems(
            [new AffineRegistration("a", "b", Matrix.identity)],
            false,
        );
        registration.recomputePathsNow();
        registration.setPosition("a", { x: 1, y: 2, index: 0 });
        expect(registration.getPosition("b")).toEqual({
            x: 1,
            y: 2,
            index: 0,
        });

        registration.recomputePathsNow();

        expect(registration.getPosition("a")).toEqual({
            x: 1,
            y: 2,
            index: 0,
        });
        expect(registration.getPosition("b")).toEqual({
            x: 1,
            y: 2,
            index: 0,
        });
    });

    it("bumps for a late patient-level import, so consumers re-resolve", () => {
        const registration = new Registration();
        registration.importRegistrationItems(
            [new AffineRegistration("fundus", "oct1_proj", Matrix.identity)],
            false,
        );
        const before = registration.revision;

        expect(registration.listDirectTargets("other")).toEqual([]);
        registration.importRegistrationItems(
            [new AffineRegistration("other", "oct2_proj", Matrix.identity)],
            false,
        );

        expect(registration.revision).toBeGreaterThan(before);
        expect(registration.listDirectTargets("other")).toEqual(["oct2_proj"]);
    });
});
