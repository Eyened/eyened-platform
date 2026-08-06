import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MainViewerContext } from "./MainViewerContext.svelte";
import type { EnfaceProjectionManager } from "$lib/viewer-window/enfaceProjectionManager.svelte";
import type { ViewerContext } from "../viewerContext.svelte";
import type { RenderTarget } from "$lib/webgl/types";

const { getOrCompile, getShaderTemplateCache, getBaseUniforms } = vi.hoisted(
    () => ({
        getOrCompile: vi.fn(),
        getShaderTemplateCache: vi.fn(),
        getBaseUniforms: vi.fn(() => ({ u_base: "base" })),
    }),
);

vi.mock("$lib/webgl/shaderTemplate", () => ({ getShaderTemplateCache }));

vi.mock("$lib/webgl/imageRenderer", () => ({ getBaseUniforms }));

import {
    EnfaceProjectionOverlay,
    type EnfaceOverlayPaintSource,
} from "./EnfaceProjectionOverlay";

function source(
    mode: EnfaceOverlayPaintSource["mode"],
    mappingGlsl: string,
    alpha = 0.5,
): EnfaceOverlayPaintSource {
    return {
        octPublicId: mappingGlsl,
        manager: {
            getVisibleProjections: () => [
                {
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
    };
}

describe("EnfaceProjectionOverlay", () => {
    beforeEach(() => {
        getOrCompile.mockReset();
        getShaderTemplateCache.mockReset();
        getShaderTemplateCache.mockReturnValue({ getOrCompile });
        getBaseUniforms.mockClear();
        getBaseUniforms.mockReturnValue({ u_base: "base" });
    });

    it("renders every enabled source with its mapped program and dimensions", () => {
        const firstPass = vi.fn();
        const secondPass = vi.fn();
        getOrCompile
            .mockReturnValueOnce({ pass: firstPass })
            .mockReturnValueOnce({ pass: secondPass });
        const overlay = new EnfaceProjectionOverlay([
            source("binary", "first"),
            source("off", "disabled"),
            source("heatmap", "second"),
        ]);
        const viewerContext = {
            image: { webgl: "webgl" },
        } as unknown as ViewerContext;
        const renderTarget = {} as RenderTarget;

        overlay.repaint(viewerContext, renderTarget);

        expect(getOrCompile).toHaveBeenCalledTimes(2);
        expect(getOrCompile.mock.calls.map((call) => call[2])).toEqual([
            { mapping: "first" },
            { mapping: "second" },
        ]);
        expect(firstPass).toHaveBeenCalledWith(
            renderTarget,
            expect.objectContaining({
                u_base: "base",
                u_mode: 0,
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
                u_min_thickness: 2,
                u_max_thickness: 8,
            }),
        );
    });

    it("skips a source whose mapped shader fails to compile", () => {
        const pass = vi.fn();
        getOrCompile
            .mockImplementationOnce(() => {
                throw new Error("compile failed");
            })
            .mockReturnValueOnce({ pass });
        const overlay = new EnfaceProjectionOverlay([
            source("binary", "broken"),
            source("binary", "valid"),
        ]);

        overlay.repaint(
            { image: { webgl: "webgl" } } as unknown as ViewerContext,
            {} as RenderTarget,
        );

        expect(getOrCompile).toHaveBeenCalledTimes(2);
        expect(pass).toHaveBeenCalledOnce();
    });

    it("skips a source whose shader is negative-cached as null", () => {
        const pass = vi.fn();
        getOrCompile.mockReturnValueOnce(null).mockReturnValueOnce({ pass });
        const overlay = new EnfaceProjectionOverlay([
            source("binary", "known-bad"),
            source("binary", "valid"),
        ]);

        overlay.repaint(
            { image: { webgl: "webgl" } } as unknown as ViewerContext,
            {} as RenderTarget,
        );

        expect(getOrCompile).toHaveBeenCalledTimes(2);
        expect(pass).toHaveBeenCalledOnce();
    });

    it("looks the program cache up on the webgl context instead of owning one", () => {
        getOrCompile.mockReturnValue({ pass: vi.fn() });
        const viewerContext = {
            image: { webgl: "webgl" },
        } as unknown as ViewerContext;

        new EnfaceProjectionOverlay([source("binary", "shared")]).repaint(
            viewerContext,
            {} as RenderTarget,
        );
        new EnfaceProjectionOverlay([source("heatmap", "shared")]).repaint(
            viewerContext,
            {} as RenderTarget,
        );

        expect(getShaderTemplateCache.mock.calls).toEqual([
            ["webgl"],
            ["webgl"],
        ]);
    });
});
