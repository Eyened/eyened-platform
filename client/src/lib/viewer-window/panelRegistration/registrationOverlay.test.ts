import { fireEvent, render, screen } from "@testing-library/svelte";
import { formAnnotations } from "$lib/data/stores.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/viewer/Viewer.svelte", () => ({
    default: () => null,
}));

vi.mock("$lib/viewer/viewerContext.svelte", () => ({
    ViewerContext: class {
        constructor(
            public image: unknown,
            public viewerWindowContext: unknown,
        ) {}
        addOverlay() {
            return () => {};
        }
    },
}));

vi.mock("$lib/webgl/affineBlendRenderer", async () => {
    const actual = await vi.importActual<
        typeof import("$lib/webgl/affineBlendRenderer")
    >("$lib/webgl/affineBlendRenderer");
    return {
        ...actual,
        AffineBlendRenderer: class {
            setPair = vi.fn();
            setTint = vi.fn();
            dispose = vi.fn();
        },
    };
});

vi.mock("$lib/webgl/seriesBlendRenderer", () => ({
    SeriesBlendRenderer: class {
        setLayers = vi.fn();
        setWeights = vi.fn();
        dispose = vi.fn();
    },
}));

const { default: RegistrationEditor } = await import(
    "./RegistrationEditor.svelte"
);
const { default: SeriesBlendEditor } = await import(
    "./SeriesBlendEditor.svelte"
);

function image(id: string): AbstractImage {
    return {
        image_id: id,
        instance: { id: `public-${id}` },
        webgl: {},
        width: 8,
        height: 8,
    } as unknown as AbstractImage;
}

const fixed = image("fixed");
const moving = image("moving");

function windowContext(overrides: Record<string, unknown> = {}) {
    return {
        topViewers: new Map<AbstractImage, unknown>([
            [fixed, {}],
            [moving, {}],
        ]),
        registration: {
            revision: 1,
            getRegistrationItem: () => undefined,
            getPath: () => null,
        },
        registrationEditor: {
            imageIds: ["fixed", "moving"],
            annotationId: 21,
        },
        seriesBlend: null,
        closeRegistrationEditor: vi.fn(),
        closeSeriesBlend: vi.fn(),
        ...overrides,
    };
}

describe("registration overlays", () => {
    beforeEach(() => {
        formAnnotations.clear();
        formAnnotations.set(21, {
            id: 21,
            form_data: {},
        } as never);
    });

    it("shows the two-image editor and closes it", async () => {
        const viewerWindowContext = windowContext();
        render(RegistrationEditor, {
            context: new Map<string, unknown>([
                ["viewerWindowContext", viewerWindowContext],
                ["globalContext", { canEdit: () => true }],
            ]),
        });

        expect(
            screen.getByRole("dialog", { name: "Registration editor" }),
        ).toBeInTheDocument();
        expect(screen.getByLabelText("Fixed tint")).toBeInTheDocument();
        expect(screen.getByLabelText("Moving colour")).toBeInTheDocument();

        await fireEvent.input(screen.getByLabelText("Fixed tint"), {
            target: { value: "0.4" },
        });
        await fireEvent.input(screen.getByLabelText("Moving colour"), {
            target: { value: "#112233" },
        });
        await fireEvent.input(screen.getByLabelText("Fixed opacity"), {
            target: { value: "0.2" },
        });

        const resizer = document.querySelector(".resizer");
        if (!resizer) throw new Error("resizer missing");
        await fireEvent.pointerDown(resizer, { clientY: 40 });
        await fireEvent.pointerMove(window, { clientY: 80 });
        await fireEvent.pointerUp(window);

        await fireEvent.click(screen.getByRole("button", { name: "Close" }));
        expect(viewerWindowContext.closeRegistrationEditor).toHaveBeenCalled();
    });

    it("closes the editor when an image is no longer open", () => {
        const viewerWindowContext = windowContext({
            registrationEditor: {
                imageIds: ["gone"],
                annotationId: 21,
            },
        });
        render(RegistrationEditor, {
            context: new Map<string, unknown>([
                ["viewerWindowContext", viewerWindowContext],
                ["globalContext", { canEdit: () => false }],
            ]),
        });
        expect(viewerWindowContext.closeRegistrationEditor).toHaveBeenCalled();
    });

    it("shows the series blend and updates the slider", async () => {
        const viewerWindowContext = windowContext({
            registrationEditor: null,
            seriesBlend: { imageIds: ["fixed", "moving"] },
        });
        render(SeriesBlendEditor, {
            context: new Map<string, unknown>([
                ["viewerWindowContext", viewerWindowContext],
            ]),
        });

        expect(
            screen.getByRole("dialog", { name: "Series blend" }),
        ).toBeInTheDocument();
        await fireEvent.input(
            screen.getByRole("slider", { name: "Series blend" }),
            {
                target: { value: "0.6" },
            },
        );
        await fireEvent.input(screen.getByLabelText("Opacity public-fixed"), {
            target: { value: "0.3" },
        });

        const resizer = document.querySelector(".resizer");
        if (!resizer) throw new Error("resizer missing");
        await fireEvent.pointerDown(resizer, { clientY: 20 });
        await fireEvent.pointerMove(window, { clientY: 50 });
        await fireEvent.pointerUp(window);

        await fireEvent.click(screen.getByRole("button", { name: "Close" }));
        expect(viewerWindowContext.closeSeriesBlend).toHaveBeenCalled();
    });

    it("closes the series blend when an image is no longer open", () => {
        const viewerWindowContext = windowContext({
            registrationEditor: null,
            seriesBlend: { imageIds: ["gone", "fixed"] },
        });
        render(SeriesBlendEditor, {
            context: new Map<string, unknown>([
                ["viewerWindowContext", viewerWindowContext],
            ]),
        });
        expect(viewerWindowContext.closeSeriesBlend).toHaveBeenCalled();
    });
});
