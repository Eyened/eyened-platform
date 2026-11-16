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
