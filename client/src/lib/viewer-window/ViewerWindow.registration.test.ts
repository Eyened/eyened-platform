import { render } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

vi.mock("@cornerstonejs/codec-openjpeg/decodewasmjs", () => ({
    default: () =>
        Promise.resolve({
            J2KDecoder: class {
                getEncodedBuffer(n: number) {
                    return new Uint8Array(n);
                }
                decode() {}
                getFrameInfo() {
                    return {
                        width: 0,
                        height: 0,
                        bitsPerSample: 8,
                        componentCount: 1,
                        isSigned: false,
                    };
                }
                getDecodedBuffer() {
                    return new Uint8Array();
                }
            },
        }),
}));
vi.mock("@cornerstonejs/codec-openjpeg/decodewasm?url", () => ({
    default: "/mock-openjpeg.wasm",
}));
vi.mock("./TopRowImages.svelte", () => ({ default: () => null }));
vi.mock("./MainPanel.svelte", () => ({ default: () => null }));
vi.mock("./RegistrationItemLoader.svelte", () => ({ default: () => null }));
vi.mock("./panelRegistration/RegistrationEditor.svelte", () => ({
    default: () => null,
}));
vi.mock("./panelRegistration/SeriesBlendEditor.svelte", () => ({
    default: () => null,
}));

const { default: ViewerWindow } = await import("./ViewerWindow.svelte");

function renderWindow(sessions: {
    registrationEditor: unknown;
    seriesBlend: unknown;
}) {
    return render(ViewerWindow, {
        props: {
            viewerWindowContext: {
                registration: {},
                instanceIds: [],
                mainPanels: [],
                ...sessions,
            },
        },
    });
}

describe("ViewerWindow registration overlays", () => {
    it("hides the main layout and mounts both overlay hosts", () => {
        const { container } = renderWindow({
            registrationEditor: { imageIds: ["a"], annotationId: 1 },
            seriesBlend: { imageIds: ["a", "b"] },
        });
        expect(container.querySelector("#main")).toHaveClass("main-hidden");
    });

    it("shows the main layout when no overlay is open", () => {
        const { container } = renderWindow({
            registrationEditor: null,
            seriesBlend: null,
        });
        expect(container.querySelector("#main")).not.toHaveClass("main-hidden");
    });
});
