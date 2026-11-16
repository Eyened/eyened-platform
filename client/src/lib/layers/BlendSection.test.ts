import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { formAnnotations } from "$lib/data/stores.svelte";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import { defaultBlendStyle } from "./blendStyles";
import { eyeKey } from "./pointsets";
import { fakeImage, layersContexts } from "./testContexts";

const fakes = vi.hoisted(() => ({ linked: new Set<string>() }));
vi.mock("$lib/registration/glslPathBetween", () => ({
    glslPathBetween: (_r: unknown, from: string, to: string) =>
        from === to || fakes.linked.has(to) ? `map-${to}` : null,
}));

const { default: BlendSection } = await import("./BlendSection.svelte");
const { ViewportBlend } = await import("./viewportBlend.svelte");

const EYE = eyeKey({ patient: { id: 1 }, laterality: "R" });
const tri = [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 0, y: 10 },
];

afterEach(() => {
    cleanup();
    formAnnotations.clear();
    fakes.linked.clear();
    vi.unstubAllGlobals();
});

function renderBlend({
    cap = 16,
    images = [
        fakeImage("inst-2"),
        fakeImage("inst-3", { modality: "ColorFundus", date: "2020-06-03" }),
    ],
} = {}) {
    const ctx = layersContexts("inst-1", { images });
    const blend = new ViewportBlend(
        ctx.viewerContext.image as never,
        ctx.win as never,
        () => ctx.workspace.catalogue,
        cap,
        false,
    );
    const view = render(BlendSection, {
        props: { blend, open: true, ontoggle: vi.fn() },
        context: ctx.context,
    });
    return { ...ctx, ...view, blend };
}

describe("BlendSection, pair modes", () => {
    it("asks for a current registration only in pair modes, then offers With on the registration's first image; passes axe", async () => {
        formAnnotations.set(12, {
            id: 12,
            form_data: { "inst-1": tri, "inst-2": tri },
        } as never);
        const { win, blend, container } = renderBlend();
        blend.setMode("overlay");
        expect(
            await screen.findByText(
                "Make a registration current in Pointsets.",
            ),
        ).toBeInTheDocument();
        blend.setMode("series");
        await vi.waitFor(() =>
            expect(
                screen.queryByText("Make a registration current in Pointsets."),
            ).toBeNull(),
        );
        win.pointsets.setCurrent(EYE, 12);
        blend.setMode("overlay");
        const field = await screen.findByRole("button", { name: /With/ });
        expect(field).toHaveTextContent("FAF 2024-03-12");
        await expectNoAxeViolations(container);
    });

    it("disables Swap while the flicker plays, and both buttons under 3 pairs", async () => {
        vi.stubGlobal("matchMedia", () => ({ matches: false }));
        formAnnotations.set(12, {
            id: 12,
            form_data: { "inst-1": tri, "inst-2": tri },
        } as never);
        const { win, blend } = renderBlend();
        win.pointsets.setCurrent(EYE, 12);
        blend.setMode("flicker");
        expect(
            await screen.findByRole("button", { name: "Swap" }),
        ).toBeDisabled();
        await fireEvent.click(
            screen.getByRole("button", { name: "Pause flicker" }),
        );
        expect(screen.getByRole("button", { name: "Swap" })).toBeEnabled();
        blend.pause();
        formAnnotations.set(12, {
            id: 12,
            form_data: { "inst-1": tri, "inst-2": [tri[0]] },
        } as never);
        await vi.waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Play flicker" }),
            ).toBeDisabled(),
        );
        expect(screen.getByRole("button", { name: "Swap" })).toBeDisabled();
    });

    it("Reset gives the other image its starting look back", async () => {
        formAnnotations.set(12, {
            id: 12,
            form_data: { "inst-1": tri, "inst-2": tri },
        } as never);
        const { win, blend } = renderBlend();
        win.pointsets.setCurrent(EYE, 12);
        win.blendStyles.set("inst-2", "other", {
            colour: "#ffffff",
            opacity: 0.2,
            invert: true,
        });
        blend.setMode("overlay");
        await fireEvent.click(
            await screen.findByRole("button", { name: "Reset" }),
        );
        expect(win.blendStyles.get("inst-2", "other")).toEqual(
            defaultBlendStyle("other"),
        );
    });
});

describe("BlendSection, Series", () => {
    /** This CF (2022), a CF of 2020 and a FAF of 2024 registered to it; a CF of 2023 that is not. */
    function series(cap = 16) {
        fakes.linked.add("inst-2");
        fakes.linked.add("inst-3");
        const view = renderBlend({
            cap,
            images: [
                fakeImage("inst-2"),
                fakeImage("inst-3", {
                    modality: "ColorFundus",
                    date: "2020-06-03",
                }),
                fakeImage("inst-4", {
                    modality: "ColorFundus",
                    date: "2023-01-01",
                }),
            ],
        });
        view.blend.setMode("series");
        return view;
    }

    it("lists registered images oldest first with this image's modality ticked and this image locked; passes axe", async () => {
        const { container } = series();
        const boxes = await screen.findAllByRole("checkbox");
        expect(boxes.map((b) => b.getAttribute("aria-checked"))).toEqual([
            "true",
            "true",
            "false",
        ]);
        expect(boxes[1]).toBeDisabled();
        expect(
            screen.getByText("Series · 2 registered images"),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Style, CF 2022-05-10" }),
        ).toBeEnabled();
        expect(screen.queryByText(/2023-01-01/)).toBeNull();
        await expectNoAxeViolations(container);
    });

    it("steps with Next, Page Up and Previous, and a double-click on the handle returns to this image", async () => {
        const { blend } = series();
        await fireEvent.click((await screen.findAllByRole("checkbox"))[2]!); // tick the FAF
        const slider = screen.getByRole("slider", { name: "Position" });
        expect(slider).toHaveAttribute("aria-valuetext", "2022-05-10");
        await fireEvent.keyDown(slider, { key: "PageUp" });
        expect(blend.showing?.image_id).toBe("inst-2");
        await fireEvent.click(
            screen.getByRole("button", { name: "Previous image" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "Previous image" }),
        );
        expect(blend.showing?.image_id).toBe("inst-3");
        await fireEvent.dblClick(slider);
        expect(blend.showing?.image_id).toBe("inst-1");
    });

    it("disables unticked images at the device limit and asks for a second image when only this one is ticked", async () => {
        series(2);
        const boxes = await screen.findAllByRole("checkbox");
        expect(boxes[2]).toBeDisabled();
        expect(
            screen.getByText("At most 2 images at once on this device"),
        ).toBeInTheDocument();
        await fireEvent.click(boxes[0]!); // untick the 2020 CF
        expect(
            await screen.findByText("Tick another image to walk a series."),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Next image" }),
        ).toBeDisabled();
    });

    it("says so when no other loaded image is registered to this one", async () => {
        const { blend } = renderBlend();
        blend.setMode("series");
        expect(
            await screen.findByText(
                "No other loaded image of this eye is registered to this one.",
            ),
        ).toBeInTheDocument();
    });

    it("a Style popover changes only its own image", async () => {
        const { win } = series();
        await fireEvent.click(
            await screen.findByRole("button", {
                name: "Style, FAF 2024-03-12",
            }),
        );
        await fireEvent.click(
            await screen.findByRole("checkbox", { name: "Invert" }),
        );
        expect(win.blendStyles.get("inst-2", "series").invert).toBe(true);
        expect(win.blendStyles.get("inst-3", "series").invert).toBe(false);
    });
});
