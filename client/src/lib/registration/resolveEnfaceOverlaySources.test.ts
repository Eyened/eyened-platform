import { describe, it, expect } from "vitest";
import { Registration } from "./registration.svelte";
import { AffineRegistration } from "./affine";
import { ParabolicRegistration } from "./parabolic";
import { Matrix } from "$lib/matrix";
import { resolveEnfaceOverlaySources } from "./resolveEnfaceOverlaySources";
import { EnfaceToProjPhotolocations } from "./enfaceToProj";
import { LinePhotoLocator } from "./photoLocators";
import type { EnfaceProjectionManager } from "$lib/viewer-window/enfaceProjectionManager.svelte";

function fakeManager(octId: string, width = 100, depth = 50) {
    return {
        octImage: { width, height: 200, depth },
    } as unknown as EnfaceProjectionManager;
}

const sizes = new Map<string, [number, number]>([
    ["fundus", [200, 200]],
    ["ir", [150, 150]],
    ["oct1_proj", [100, 50]],
]);

function getImageSize(id: string) {
    return sizes.get(id);
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
            getImageSize,
            projMode: "binary",
            linkedModes: new Map(),
        });
        expect(sources).toHaveLength(1);
        expect(sources[0].octPublicId).toBe("oct1");
        expect(sources[0].mappingGlsl).toContain("return uv;");
        expect(sources[0].mode).toBe("binary");
    });

    it("includes direct affine and parabolic edges to _proj", () => {
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
            getImageSize,
            projMode: "binary",
            linkedModes: new Map([["oct1", "heatmap"]]),
        });
        expect(sources).toHaveLength(2);
        const byOct = Object.fromEntries(
            sources.map((s) => [s.octPublicId, s]),
        );
        expect(byOct.oct1.mode).toBe("heatmap");
        expect(byOct.oct1.mappingGlsl).toContain("map_0");
        expect(byOct.oct1.sizePrimary).toEqual([200, 200]);
        expect(byOct.oct1.sizeSecondary).toEqual([100, 50]);
        expect(byOct.oct2.mode).toBe("off");
        expect(byOct.oct2.mappingGlsl).toContain("dx_val");
    });

    it("composes affine + enface→proj along a multi-hop path", () => {
        const registration = new Registration();
        const locators = [
            new LinePhotoLocator(
                "ir",
                "oct1",
                { x: 0, y: 0 },
                { x: 150, y: 0 },
                0,
                100,
            ),
        ];
        registration.importRegistrationItems(
            [
                new AffineRegistration("fundus", "ir", Matrix.identity),
                new EnfaceToProjPhotolocations(
                    "ir",
                    "oct1_proj",
                    locators,
                    100,
                    50,
                ),
            ],
            false,
        );
        registration.recomputePathsNow();

        const sources = resolveEnfaceOverlaySources({
            imageId: "fundus",
            imageWidth: 200,
            imageHeight: 200,
            registration,
            managers: new Map([["oct1", fakeManager("oct1")]]),
            getImageSize,
            projMode: "binary",
            linkedModes: new Map([["oct1", "binary"]]),
        });
        expect(sources).toHaveLength(1);
        expect(sources[0].mappingGlsl).toContain("map_0");
        expect(sources[0].mappingGlsl).toContain("map_1");
        expect(sources[0].mappingGlsl).toContain("bestDist");
    });

    it("composes parabolic + enface→proj along a multi-hop path", () => {
        const registration = new Registration();
        const locators = [
            new LinePhotoLocator(
                "ir",
                "oct1",
                { x: 0, y: 0 },
                { x: 150, y: 0 },
                0,
                100,
            ),
        ];
        registration.importRegistrationItems(
            [
                new ParabolicRegistration(
                    "fundus",
                    "ir",
                    [0.1, 0, 0, 0, 0, 0, 0],
                    [0, 0.2, 0, 0, 0, 0, 0],
                ),
                new EnfaceToProjPhotolocations(
                    "ir",
                    "oct1_proj",
                    locators,
                    100,
                    50,
                ),
            ],
            false,
        );
        registration.recomputePathsNow();

        const sources = resolveEnfaceOverlaySources({
            imageId: "fundus",
            imageWidth: 200,
            imageHeight: 200,
            registration,
            managers: new Map([["oct1", fakeManager("oct1")]]),
            getImageSize,
            projMode: "binary",
            linkedModes: new Map([["oct1", "binary"]]),
        });
        expect(sources).toHaveLength(1);
        expect(sources[0].mappingGlsl).toContain("map_0");
        expect(sources[0].mappingGlsl).toContain("map_1");
        expect(sources[0].mappingGlsl).toContain("dx_val");
        expect(sources[0].mappingGlsl).toContain("bestDist");
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
            getImageSize: () => [10, 10],
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
            getImageSize: () => [10, 10],
            projMode: "binary",
            linkedModes: new Map([["oct1", "binary"]]),
        });
        expect(sources).toHaveLength(0);
    });

    it("skips paths when an intermediate image size is unknown", () => {
        const registration = new Registration();
        registration.importRegistrationItems(
            [
                new AffineRegistration("fundus", "ir", Matrix.identity),
                new EnfaceToProjPhotolocations(
                    "ir",
                    "oct1_proj",
                    [
                        new LinePhotoLocator(
                            "ir",
                            "oct1",
                            { x: 0, y: 0 },
                            { x: 10, y: 0 },
                            0,
                            100,
                        ),
                    ],
                    100,
                    50,
                ),
            ],
            false,
        );
        registration.recomputePathsNow();
        const sources = resolveEnfaceOverlaySources({
            imageId: "fundus",
            imageWidth: 200,
            imageHeight: 200,
            registration,
            managers: new Map([["oct1", fakeManager("oct1")]]),
            getImageSize: (id) => (id === "fundus" ? [200, 200] : undefined),
            projMode: "binary",
            linkedModes: new Map([["oct1", "binary"]]),
        });
        expect(sources).toHaveLength(0);
    });
});
