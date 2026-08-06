import { describe, it, expect } from "vitest";
import { Registration } from "./registration";
import { AffineRegistration } from "./affine";
import { ParabolicRegistration } from "./parabolic";
import { Matrix } from "$lib/matrix";
import { resolveEnfaceOverlaySources } from "./resolveEnfaceOverlaySources";
import type { EnfaceProjectionManager } from "$lib/viewer-window/enfaceProjectionManager.svelte";

function fakeManager(octId: string, width = 100, depth = 50) {
    return {
        octImage: { width, height: 200, depth },
    } as unknown as EnfaceProjectionManager;
}

describe("resolveEnfaceOverlaySources", () => {
    it("returns identity source for _proj", () => {
        const registration = new Registration();
        const managers = new Map([["oct1", fakeManager("oct1")]]);
        const sources = resolveEnfaceOverlaySources({
            imageId: "oct1_proj",
            imageWidth: 100,
            imageHeight: 50,
            registration,
            managers,
            projMode: "binary",
            linkedModes: new Map(),
        });
        expect(sources).toHaveLength(1);
        expect(sources[0].octPublicId).toBe("oct1");
        expect(sources[0].mappingGlsl).toContain("return uv;");
        expect(sources[0].mode).toBe("binary");
    });

    it("includes direct affine edges to _proj only", () => {
        const registration = new Registration();
        registration.importRegistrationItems(
            [
                new AffineRegistration(
                    "fundus",
                    "oct1_proj",
                    new Matrix(1, 0, 0, 0, 1, 0, 0, 0, 1),
                ),
                new ParabolicRegistration(
                    "fundus",
                    "oct2_proj",
                    [0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0],
                ),
            ],
            false,
        );
        registration.recomputePathsNow();
        const managers = new Map([
            ["oct1", fakeManager("oct1")],
            ["oct2", fakeManager("oct2")],
        ]);
        const sources = resolveEnfaceOverlaySources({
            imageId: "fundus",
            imageWidth: 200,
            imageHeight: 200,
            registration,
            managers,
            projMode: "binary",
            linkedModes: new Map([["oct1", "heatmap"]]),
        });
        expect(sources).toHaveLength(1);
        expect(sources[0].octPublicId).toBe("oct1");
        expect(sources[0].mode).toBe("heatmap");
        expect(sources[0].mappingGlsl).toContain("map_0");
        expect(sources[0].sizePrimary).toEqual([200, 200]);
        expect(sources[0].sizeSecondary).toEqual([100, 50]);
    });

    it("defaults linked mode to off", () => {
        const registration = new Registration();
        registration.importRegistrationItems(
            [new AffineRegistration("fundus", "oct1_proj", Matrix.identity)],
            false,
        );
        registration.recomputePathsNow();
        const sources = resolveEnfaceOverlaySources({
            imageId: "fundus",
            imageWidth: 10,
            imageHeight: 10,
            registration,
            managers: new Map([["oct1", fakeManager("oct1")]]),
            projMode: "binary",
            linkedModes: new Map(),
        });
        expect(sources[0].mode).toBe("off");
    });

    it("omits sources without a loaded manager", () => {
        const registration = new Registration();
        registration.importRegistrationItems(
            [new AffineRegistration("fundus", "oct1_proj", Matrix.identity)],
            false,
        );
        registration.recomputePathsNow();
        const sources = resolveEnfaceOverlaySources({
            imageId: "fundus",
            imageWidth: 10,
            imageHeight: 10,
            registration,
            managers: new Map(),
            projMode: "binary",
            linkedModes: new Map([["oct1", "binary"]]),
        });
        expect(sources).toHaveLength(0);
    });
});
