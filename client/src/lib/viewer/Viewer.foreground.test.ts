import { render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));

import Viewer from "./Viewer.svelte";

describe("Viewer foreground registration", () => {
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("registers a foreground viewer and leaves the info panel off", () => {
        vi.stubGlobal(
            "ResizeObserver",
            class {
                observe() {}
                disconnect() {}
            },
        );
        const canvas = document.createElement("canvas");
        const addViewer = vi.fn(() => vi.fn());
        const viewerContext = {
            canvas2D: canvas,
            image: { is3D: false, orientation: "enface" },
            initTransform: vi.fn(),
        };
        render(Viewer, {
            props: { showInfo: false, foreground: true },
            context: new Map<string, unknown>([
                ["viewerContext", viewerContext],
                ["viewerWindowContext", { addViewer }],
            ]),
        });
        expect(addViewer).toHaveBeenCalledWith(viewerContext, true);
        expect(document.querySelector(".info")).toBeNull();
    });
});
