import { fireEvent, render, screen } from "@testing-library/svelte";
import { formAnnotations } from "$lib/data/stores.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { AffineRegistration } from "$lib/registration/affine";
import { Matrix } from "$lib/matrix";
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

const renderers = vi.hoisted(
    () =>
        [] as {
            setLayers: ReturnType<typeof vi.fn>;
            setComposite: ReturnType<typeof vi.fn>;
        }[],
);

vi.mock("$lib/webgl/blendRenderer", () => ({
    BlendRenderer: class {
        setLayers = vi.fn();
        setComposite = vi.fn();
        dispose = vi.fn();
        constructor() {
            renderers.push(this);
        }
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
        await fireEvent.change(screen.getByLabelText("Moving render mode"), {
            target: { value: "CLAHE" },
        });

        const renderer = renderers.at(-1)!;
        const [fixedLayer, movingLayer] = renderer.setLayers.mock.lastCall![0];
        expect(fixedLayer.style).toMatchObject({
            tint: 0.4,
            colour: "#ff0000",
            opacity: 0.2,
        });
        expect(movingLayer.style).toMatchObject({
            colour: "#112233",
            renderMode: "CLAHE",
        });
        expect(movingLayer.mapping).toEqual({ affine: null });
        expect(renderer.setComposite).toHaveBeenLastCalledWith("overlay", 64);

        expect(
            screen.queryByLabelText("Checkerboard tile size"),
        ).not.toBeInTheDocument();
        await fireEvent.click(screen.getByLabelText("Checkerboard"));
        await fireEvent.input(screen.getByLabelText("Checkerboard tile size"), {
            target: { value: "128" },
        });
        expect(renderer.setComposite).toHaveBeenLastCalledWith(
            "checkerboard",
            128,
        );

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

    it("follows the open annotation affine instead of another graph edge", async () => {
        const graphMatrix = new Matrix(9, 0, 0, 0, 9, 0);
        formAnnotations.set(21, {
            id: 21,
            form_data: {
                fixed: [
                    { x: 0, y: 0 },
                    { x: 10, y: 0 },
                    { x: 0, y: 10 },
                ],
                moving: [
                    { x: 5, y: 7 },
                    { x: 25, y: 7 },
                    { x: 5, y: 27 },
                ],
            },
        } as never);
        const viewerWindowContext = windowContext({
            registration: {
                revision: 1,
                getRegistrationItem: () =>
                    new AffineRegistration("fixed", "moving", graphMatrix),
                getPath: () => ["fixed", "moving"],
            },
        });
        render(RegistrationEditor, {
            context: new Map<string, unknown>([
                ["viewerWindowContext", viewerWindowContext],
                ["globalContext", { canEdit: () => true }],
            ]),
        });

        const renderer = renderers.at(-1)!;
        const movingLayer = renderer.setLayers.mock.lastCall![0][1];
        expect(movingLayer.mapping.affine).not.toBe(graphMatrix);
        expect(movingLayer.mapping.affine.apply({ x: 0, y: 0 }).x).toBeCloseTo(
            5,
        );
        expect(movingLayer.mapping.affine.apply({ x: 0, y: 0 }).y).toBeCloseTo(
            7,
        );
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
        await fireEvent.input(screen.getByLabelText("public-fixed opacity"), {
            target: { value: "0.3" },
        });
        await fireEvent.input(screen.getByLabelText("public-moving tint"), {
            target: { value: "1" },
        });

        const renderer = renderers.at(-1)!;
        const layers = renderer.setLayers.mock.lastCall![0];
        expect(layers.map((layer: { weight: number }) => layer.weight)).toEqual(
            [0.4, 0.6],
        );
        expect(layers[0].style).toMatchObject({ opacity: 0.3, tint: 0 });
        expect(layers[1].style).toMatchObject({ opacity: 1, tint: 1 });
        expect(screen.queryByLabelText("Checkerboard")).not.toBeInTheDocument();

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
