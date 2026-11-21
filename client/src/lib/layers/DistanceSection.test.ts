import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Line } from "./distanceLines.svelte";
import type { Scale } from "./imageScale";
import { layersContexts } from "./testContexts";

const { default: DistanceSection } = await import("./DistanceSection.svelte");

afterEach(cleanup);

const SCALE: Scale = {
    x: 10,
    y: 10,
    source: "stored",
    pick: { kind: "stored" },
};

function renderSection() {
    const ctx = layersContexts("inst-1");
    const view = render(DistanceSection, {
        props: {
            distance: ctx.distance,
            scale: SCALE,
            open: true,
            ontoggle: vi.fn(),
        },
        context: ctx.context,
    });
    return { ...ctx, ...view };
}

describe("DistanceSection", () => {
    it("lists this B-scan's lines as Line n · length and focus highlights one; Delete line n removes it and focus moves on", async () => {
        const { distance } = renderSection();
        distance.add(new Line({ x: 0, y: 0 }, { x: 30, y: 40 }, 0));
        distance.add(new Line({ x: 0, y: 0 }, { x: 300, y: 400 }, 1));
        distance.add(new Line({ x: 0, y: 0 }, { x: 0, y: 200 }, 0));
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
        expect(distance.highlighted?.end).toEqual({ x: 0, y: 200 });
        await fireEvent.click(remove);
        expect(screen.queryByText(/^Line 2/)).toBeNull();
        expect(distance.lines).toHaveLength(2);
        await vi.waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Delete line 1" }),
            ).toHaveFocus(),
        );
        // Focus now sits in Line 1's row, so Line 1 is the highlighted one.
        expect(distance.highlighted?.end).toEqual({ x: 30, y: 40 });
    });
});
