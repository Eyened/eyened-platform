import { twinNumbers } from "$lib/workspace/imageMeta";
import { afterEach, describe, expect, it, vi } from "vitest";
import { formAnnotations } from "$lib/data/stores.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { BlendLayer } from "$lib/webgl/blendRenderer";
import { BlendStyles } from "./blendStyles";
import { eyeKey, PointsetState } from "./pointsets";

const fakes = vi.hoisted(() => ({
    linked: new Set<string>(),
    failCompile: false,
}));

vi.mock("$lib/webgl/blendRenderer", () => ({
    BlendRenderer: class {
        layers: unknown[] = [];
        setLayers(layers: unknown[]) {
            if (fakes.failCompile) throw new Error("compile failed");
            this.layers = layers;
        }
        setComposite = vi.fn();
        dispose = vi.fn();
    },
}));
vi.mock("$lib/registration/glslPathBetween", () => ({
    glslPathBetween: (_r: unknown, from: string, to: string) =>
        from === to || fakes.linked.has(to) ? `map-${to}` : null,
}));

const { ViewportBlend } = await import("./viewportBlend.svelte");

/** A synthetic loaded 2D image of patient 1's right eye. */
function img(id: string, modality = "ColorFundus", date = "2022-05-10") {
    return {
        image_id: id,
        is2D: true,
        width: 100,
        height: 100,
        instance: {
            id,
            patient: { id: 1 },
            laterality: "R",
            modality,
            study: { date },
            device: {},
        },
    } as unknown as AbstractImage;
}
const A = img("a");
const B = img("b", "Autofluorescence", "2024-03-12");
const C = img("c", "ColorFundus", "2020-06-03");
const D = img("d", "ColorFundus", "2023-01-01");
const EYE = eyeKey({ patient: { id: 1 }, laterality: "R" });
const tri = [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 0, y: 10 },
];

function registration(id: number, form_data: Record<string, unknown>) {
    formAnnotations.set(id, { id, form_data } as never);
}

function setup(images = [A, B, C], { cap = 16, hidden = false } = {}) {
    const win = {
        pointsets: new PointsetState(),
        blendStyles: new BlendStyles(),
        images: new Map(images.map((i) => [i.image_id, i])),
        registration: { revision: 0 },
        topViewers: new Map(),
        twins: twinNumbers(
            images.map((i) => i.image_id),
            (id) => images.find((i) => i.image_id === id)?.instance as never,
        ),
    };
    const blend = new ViewportBlend(
        images[0]!,
        win as never,
        () => images.map((i) => i.image_id),
        cap,
        hidden,
    );
    return { win, blend };
}

/** A viewport with its own W/L and the renderer it starts with. */
const viewer = () =>
    ({
        imageRenderer: "base",
        renderMode: "Original",
        windowLevel: { min: 30, max: 220 },
    }) as never;
const drawn = (vc: { imageRenderer: unknown }) =>
    (vc.imageRenderer as { layers: BlendLayer[] }).layers;

afterEach(() => {
    formAnnotations.clear();
    fakes.linked.clear();
    fakes.failCompile = false;
    vi.useRealTimers();
    vi.unstubAllGlobals();
});

describe("ViewportBlend", () => {
    it("titles a pair blend with the other image's name line, #2 for a retake", () => {
        const B2 = img("b2", "Autofluorescence", "2024-03-12");
        registration(12, { a: tri, b2: tri });
        const { win, blend } = setup([A, B, B2]);
        win.pointsets.setCurrent(EYE, 12);
        blend.setMode("overlay");
        expect(blend.titleSuffix).toBe(" · blended with FAF · 2024-03-12 #2");
    });

    it("swaps in a BlendRenderer with the viewport's W/L on this image, and Off puts the viewer's renderer back", () => {
        registration(12, { a: tri, b: tri });
        const { win, blend } = setup();
        win.pointsets.setCurrent(EYE, 12);
        const vc = viewer();
        blend.setMode("overlay");
        blend.apply(vc);
        const layers = drawn(vc);
        expect(layers.map((l) => l.image)).toEqual([A, B]);
        expect(layers[0]!.style).toMatchObject({
            windowLevel: { min: 30, max: 220 },
            colour: "#ff0000",
        });
        expect(layers[1]!.style.colour).toBe("#00ffff");
        expect(layers[1]!.mapping).not.toEqual({ affine: null });
        blend.setMode("off");
        blend.apply(vc);
        expect((vc as { imageRenderer: unknown }).imageRenderer).toBe("base");
    });

    it("turns Off and flags the error when the blend shader fails to compile", () => {
        registration(12, { a: tri, b: tri });
        const { win, blend } = setup();
        win.pointsets.setCurrent(EYE, 12);
        fakes.failCompile = true;
        const vc = viewer();
        blend.setMode("overlay");
        blend.apply(vc);
        expect(blend.mode).toBe("off");
        expect(blend.error).toBe(true);
        expect((vc as { imageRenderer: unknown }).imageRenderer).toBe("base");
    });

    it("keeps With on its image when another registration with it becomes current, else takes that one's first; with none current the mode stays and only this image draws", () => {
        registration(12, { a: tri, b: tri, c: tri });
        registration(13, { a: tri, c: tri });
        registration(14, { a: tri, b: tri });
        const { win, blend } = setup();
        win.pointsets.setCurrent(EYE, 12);
        blend.setMode("overlay");
        blend.setWith("c");
        expect(blend.other).toBe(C);
        win.pointsets.setCurrent(EYE, 13);
        expect(blend.other).toBe(C);
        win.pointsets.setCurrent(EYE, 14);
        expect(blend.other).toBe(B);
        win.pointsets.setCurrent(EYE, undefined);
        expect(blend.mode).toBe("overlay");
        expect(blend.layers(viewer())).toBeNull();
        expect(blend.viewportLine).toBe(
            "Make a registration current in Pointsets.",
        );
    });

    it("under 3 pairs draws no other image and asks for the missing pairs, never borrowing another registration's path", () => {
        fakes.linked.add("b");
        registration(12, { a: tri, b: [tri[0], tri[1], null] });
        const { win, blend } = setup();
        win.pointsets.setCurrent(EYE, 12);
        blend.setMode("overlay");
        expect(blend.layers(viewer())![1]!.mapping).toEqual({ affine: null });
        expect(blend.viewportLine).toBe(
            "Place 1 more pair to line up the images",
        );
    });

    it("flickers once a second, untinted at full opacity, and starts paused when the OS asks for reduced motion", () => {
        vi.useFakeTimers();
        vi.stubGlobal("matchMedia", () => ({ matches: false }));
        registration(12, { a: tri, b: tri });
        const { win, blend } = setup();
        win.pointsets.setCurrent(EYE, 12);
        const weights = () => blend.layers(viewer())!.map((l) => l.weight);
        blend.setMode("flicker");
        expect(weights()).toEqual([1, 0]);
        vi.advanceTimersByTime(1000);
        expect(weights()).toEqual([0, 1]);
        expect(
            blend
                .layers(viewer())!
                .every((l) => l.style.tint === 0 && l.style.opacity === 1),
        ).toBe(true);
        vi.stubGlobal("matchMedia", () => ({ matches: true }));
        blend.setMode("flicker");
        expect(blend.playing).toBe(false);
        vi.advanceTimersByTime(3000);
        expect(weights()).toEqual([1, 0]);
    });

    it("keeps styles per image and role: an image starts red where it is this image and cyan where it is the other, and a change survives Off", () => {
        registration(12, { a: tri, b: tri });
        const { win, blend } = setup();
        const there = new ViewportBlend(
            B,
            win as never,
            () => ["a", "b"],
            16,
            false,
        );
        win.pointsets.setCurrent(EYE, 12);
        blend.setMode("overlay");
        there.setMode("overlay");
        expect(blend.layers(viewer())![0]!.style.colour).toBe("#ff0000");
        expect(there.layers(viewer())![1]!.style.colour).toBe("#00ffff");
        win.blendStyles.set("a", "other", { opacity: 0.4 });
        there.setMode("off");
        there.setMode("overlay");
        expect(there.layers(viewer())![1]!.style.opacity).toBe(0.4);
        expect(blend.layers(viewer())![0]!.style.opacity).toBe(1);
    });

    it("lists only images with a registration path, oldest first, starts with this image's modality ticked and on this image", () => {
        fakes.linked.add("b");
        fakes.linked.add("c");
        const { blend } = setup([A, B, C, D]);
        expect(blend.seriesItems.map((i) => i.image.image_id)).toEqual([
            "c",
            "a",
            "b",
        ]);
        expect(blend.ticked).toEqual(["a", "c"]);
        blend.setMode("series");
        const layers = blend.layers(viewer())!;
        expect(layers.map((l) => [l.image.image_id, l.weight])).toEqual([
            ["a", 1],
            ["c", 0],
        ]);
        expect(layers[0]!.style.windowLevel).toEqual({ min: 30, max: 220 });
        blend.step(-1);
        expect(blend.layers(viewer())!.map((l) => l.weight)).toEqual([0, 1]);
        expect(blend.titleSuffix).toBe(" · series · showing CF · 2020-06-03");
    });

    it("offers the Overlay drop only for an image with pairs in the current registration, and never when Registration is hidden", () => {
        registration(12, { a: tri, b: [tri[0]], c: [null] });
        const shown = setup();
        shown.win.pointsets.setCurrent(EYE, 12);
        expect(shown.blend.canOverlay("b")).toBe(true);
        expect(shown.blend.canOverlay("c")).toBe(false);
        const hidden = setup([A, B, C], { hidden: true });
        hidden.win.pointsets.setCurrent(EYE, 12);
        expect(hidden.blend.canOverlay("b")).toBe(false);
    });
});
