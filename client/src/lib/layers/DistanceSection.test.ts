import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Line } from "$lib/viewer/tools/Measure.svelte";
import { layersContexts } from "./testContexts";

const { default: DistanceSection } = await import("./DistanceSection.svelte");

afterEach(cleanup);

function renderSection() {
    const ctx = layersContexts("inst-1", {
        resolution: { x: 10, y: 10, z: 1 },
    });
    const view = render(DistanceSection, {
        props: {
            measure: ctx.measure,
            grids: ctx.grids,
            open: true,
            ontoggle: vi.fn(),
            shown: true,
        },
        context: ctx.context,
    });
    return { ...ctx, ...view };
}

describe("DistanceSection", () => {
    it("lists this B-scan's lines as Line n · length; focus highlights one; Delete line n removes it and focus moves on", async () => {
        const { measure } = renderSection();
        measure.lines.add(new Line({ x: 0, y: 0 }, { x: 30, y: 40 }, 0));
        measure.lines.add(new Line({ x: 0, y: 0 }, { x: 300, y: 400 }, 1));
        measure.lines.add(new Line({ x: 0, y: 0 }, { x: 0, y: 200 }, 0));
        await tick();
        expect(
            screen.getByRole("button", { name: "Distance lines 2" }),
        ).toBeInTheDocument();
        expect(screen.getByText("Line 1 · 500.00 µm")).toBeInTheDocument();
        expect(screen.getByText("Line 2 · 2.00 mm")).toBeInTheDocument();
        const remove = within(
            screen.getByRole("group", { name: "Line 2" }),
        ).getByRole("button", { name: "Delete line 2" });
        await fireEvent.focusIn(remove);
        expect(measure.highligtLine?.end).toEqual({ x: 0, y: 200 });
        await fireEvent.click(remove);
        expect(screen.queryByText(/^Line 2/)).toBeNull();
        expect(measure.lines.size).toBe(2);
        await vi.waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Delete line 1" }),
            ).toHaveFocus(),
        );
        // Focus now sits in Line 1's row, so Line 1 is the highlighted one.
        expect(measure.highligtLine?.end).toEqual({ x: 30, y: 40 });
    });

    it("sets the resolution from the AI grid at the fraction, and reverts a bad X", async () => {
        const ctx = layersContexts("inst-1", {
            resolution: { x: 10, y: 10, z: 1 },
            cfKeypoints: { fovea_xy: [10, 11], disc_edge_xy: [20, 21] },
        });
        render(DistanceSection, {
            props: {
                measure: ctx.measure,
                grids: ctx.grids,
                open: true,
                ontoggle: vi.fn(),
                shown: true,
            },
            context: ctx.context,
        });
        expect(screen.getByText("10.00 × 10.00 µm/px")).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Image resolution" }),
        );
        // Fovea to disc edge is sqrt(200) px; 3000 µm / 0.85 / 14.1421 px is 249.57 µm/px.
        await fireEvent.click(
            screen.getByRole("button", {
                name: "From AI grid: 249.57 µm/px",
            }),
        );
        expect(screen.getByText("249.57 × 249.57 µm/px")).toBeInTheDocument();
        const x = screen.getByLabelText("X (µm/px)");
        for (const bad of ["", "0"]) {
            await fireEvent.input(x, { target: { value: bad } });
            await fireEvent.keyDown(x, { key: "Enter" });
            expect(x).toHaveValue(ctx.measure.imageResX);
        }
        expect(ctx.measure.imageResX).toBeCloseTo(249.567, 3);
    });

    it("arms the Measure tool while open and on screen, and disarms it when closed", async () => {
        const { measure, viewerContext, rerender } = renderSection();
        expect(viewerContext.addOverlay).toHaveBeenCalledWith(measure);
        const disarm = vi.mocked(viewerContext.addOverlay).mock.results[0]
            .value as ReturnType<typeof vi.fn>;
        await rerender({ open: false });
        expect(disarm).toHaveBeenCalled();
        vi.mocked(viewerContext.addOverlay).mockClear();
        await rerender({ open: true, shown: false });
        expect(viewerContext.addOverlay).not.toHaveBeenCalled();
    });
});
