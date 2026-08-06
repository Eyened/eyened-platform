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
        expect(
            compileShaderTemplate.mock.calls.map((call) => call[2]),
        ).toEqual([{ mapping: "first" }, { mapping: "second" }]);

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
});
