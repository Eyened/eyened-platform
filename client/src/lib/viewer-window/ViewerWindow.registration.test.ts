import { render } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));
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
