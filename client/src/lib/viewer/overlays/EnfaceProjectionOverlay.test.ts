import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MainViewerContext } from "./MainViewerContext.svelte";
import type { EnfaceProjectionManager } from "$lib/viewer-window/enfaceProjectionManager.svelte";
import type { ViewerContext } from "../viewerContext.svelte";
import type { RenderTarget } from "$lib/webgl/types";
import type { WebGL } from "$lib/webgl/webgl";

const { compileShaderTemplate, getBaseUniforms } = vi.hoisted(() => ({
    compileShaderTemplate: vi.fn(),
    getBaseUniforms: vi.fn(() => ({ u_base: "base" })),
}));

vi.mock("$lib/webgl/shaderTemplate", () => ({ compileShaderTemplate }));

vi.mock("$lib/webgl/imageRenderer", () => ({ getBaseUniforms }));

import {
    EnfaceProjectionOverlay,
    type EnfaceOverlayPaintSource,
} from "./EnfaceProjectionOverlay";

function source(
    mode: EnfaceOverlayPaintSource["mode"],
    mappingGlsl: string,
    alpha = 0.5,
    identityMapping = false,
): EnfaceOverlayPaintSource {
    return {
        octPublicId: mappingGlsl,
        manager: {
            getPaintLayers: () => [
                {
                    kind: "projection",
                    projection: {
                        textureData: { texture: `${mappingGlsl}-texture` },
                        getThicknessRange: () => ({ min: 2, max: 8 }),
                    },
                    color: [255, 128, 0],
                    layerAlpha: 0.4,
                },
            ],
        } as unknown as EnfaceProjectionManager,
        mainViewerContext: { alpha } as MainViewerContext,
        mappingGlsl,
        mode,
        sizePrimary: [200, 100],
        sizeSecondary: [50, 25],
        identityMapping,
    };
}

const webgl = {} as WebGL;

describe("EnfaceProjectionOverlay", () => {
    beforeEach(() => {
        compileShaderTemplate.mockReset();
        getBaseUniforms.mockClear();
        getBaseUniforms.mockReturnValue({ u_base: "base" });
    });

    it("compiles enabled sources once in the constructor and reuses them on repaint", () => {
        const firstPass = vi.fn();
        const secondPass = vi.fn();
        compileShaderTemplate
            .mockReturnValueOnce({ pass: firstPass })
            .mockReturnValueOnce({ pass: secondPass });

        const overlay = new EnfaceProjectionOverlay(
            [
                source("binary", "first"),
                source("off", "disabled"),
                source("heatmap", "second"),
            ],
            webgl,
        );

        expect(compileShaderTemplate).toHaveBeenCalledTimes(2);
        expect(compileShaderTemplate.mock.calls.map((call) => call[2])).toEqual(
            [{ mapping: "first" }, { mapping: "second" }],
        );

        const viewerContext = {
            image: { webgl },
        } as unknown as ViewerContext;
        const renderTarget = {} as RenderTarget;

        overlay.repaint(viewerContext, renderTarget);
        overlay.repaint(viewerContext, renderTarget);

        expect(compileShaderTemplate).toHaveBeenCalledTimes(2);
        expect(firstPass).toHaveBeenCalledTimes(2);
        expect(secondPass).toHaveBeenCalledTimes(2);
        expect(firstPass).toHaveBeenCalledWith(
            renderTarget,
            expect.objectContaining({
                u_base: "base",
                u_mode: 0,
                u_nearest_sample: 0,
                u_min_thickness: 0,
                u_max_thickness: 1,
                u_alpha: 0.2,
                u_size_primary: [200, 100],
                u_size_secondary: [50, 25],
            }),
        );
        expect(secondPass).toHaveBeenCalledWith(
            renderTarget,
            expect.objectContaining({
                u_mode: 1,
                u_nearest_sample: 0,
                u_min_thickness: 2,
                u_max_thickness: 8,
            }),
        );
    });

    it("uses nearest thickness sampling only for identity _proj binary", () => {
        const binaryPass = vi.fn();
        const heatmapPass = vi.fn();
        compileShaderTemplate
            .mockReturnValueOnce({ pass: binaryPass })
            .mockReturnValueOnce({ pass: heatmapPass });

        const overlay = new EnfaceProjectionOverlay(
            [
                source("binary", "proj-id", 0.5, true),
                source("heatmap", "proj-heat", 0.5, true),
            ],
            webgl,
        );

        overlay.repaint(
            { image: { webgl } } as unknown as ViewerContext,
            {} as RenderTarget,
        );

        expect(binaryPass).toHaveBeenCalledWith(
            expect.anything(),
            expect.objectContaining({
                u_mode: 0,
                u_nearest_sample: 1,
            }),
        );
        expect(heatmapPass).toHaveBeenCalledWith(
            expect.anything(),
            expect.objectContaining({
                u_mode: 1,
                u_nearest_sample: 0,
            }),
        );
    });

    it("paints a class map nearest-sampled on a linked image, at the viewer's opacity only", () => {
        const pass = vi.fn();
        compileShaderTemplate.mockReturnValueOnce({ pass });
        const linked = source("binary", "linked");
        linked.manager = {
            getPaintLayers: () => [
                {
                    kind: "classMap",
                    texture: "map",
                    active: 2,
                    activeAlpha: 1,
                    inactiveAlpha: 0.2,
                },
            ],
        } as unknown as EnfaceProjectionManager;
        new EnfaceProjectionOverlay([linked], webgl).repaint(
            { image: { webgl } } as unknown as ViewerContext,
            {} as RenderTarget,
        );
        expect(pass).toHaveBeenCalledWith(
            expect.anything(),
            expect.objectContaining({
                u_thickness: "map",
                u_mode: 2,
                u_nearest_sample: 1,
                u_alpha: 0.5,
                u_active_class: 2,
            }),
        );
    });

    it("gives the projection and class map passes the same uniform names, as the program needs every uniform it uses", () => {
        const pass = vi.fn();
        compileShaderTemplate.mockReturnValueOnce({ pass });
        const both = source("binary", "linked");
        both.manager = {
            getPaintLayers: () => [
                {
                    kind: "projection",
                    projection: { textureData: { texture: "t" } },
                    color: [255, 0, 0],
                    layerAlpha: 1,
                },
                {
                    kind: "classMap",
                    texture: "map",
                    active: 2,
                    activeAlpha: 1,
                    inactiveAlpha: 0.2,
                },
            ],
        } as unknown as EnfaceProjectionManager;
        new EnfaceProjectionOverlay([both], webgl).repaint(
            { image: { webgl } } as unknown as ViewerContext,
            {} as RenderTarget,
        );
        const [projection, classMap] = pass.mock.calls.map(([, u]) =>
            Object.keys(u).sort(),
        );
        expect(classMap).toEqual(projection);
    });

    it("skips a source whose mapped shader fails to compile", () => {
        const pass = vi.fn();
        vi.spyOn(console, "error").mockImplementation(() => {});
        compileShaderTemplate
            .mockImplementationOnce(() => {
                throw new Error("compile failed");
            })
            .mockReturnValueOnce({ pass });

        const overlay = new EnfaceProjectionOverlay(
            [source("binary", "broken"), source("binary", "valid")],
            webgl,
        );

        overlay.repaint(
            { image: { webgl } } as unknown as ViewerContext,
            {} as RenderTarget,
        );

        expect(compileShaderTemplate).toHaveBeenCalledTimes(2);
        expect(pass).toHaveBeenCalledOnce();
    });

    it("disposes compiled programs on destroy", () => {
        const dispose = vi.fn();
        compileShaderTemplate
            .mockReturnValueOnce({ pass: vi.fn(), dispose })
            .mockReturnValueOnce({ pass: vi.fn(), dispose });

        const overlay = new EnfaceProjectionOverlay(
            [source("binary", "first"), source("heatmap", "second")],
            webgl,
        );
        overlay.destroy();

        expect(dispose).toHaveBeenCalledTimes(2);
    });
});
