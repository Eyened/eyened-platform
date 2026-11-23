import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import {
    graderSegmentation,
    layersContexts,
    ME,
} from "$lib/layers/testContexts";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import MultiFeatureSelector from "./MultiFeatureSelector.svelte";

afterEach(cleanup);

const layers = graderSegmentation(1, ME, "Retinal layers", {
    data_representation: "MultiClass",
    feature: {
        id: 101,
        name: "Retinal layers",
        subfeatures: [
            { index: 0, name: "Background" },
            { index: 1, name: "Nerve fibre layer" },
            { index: 2, name: "Ganglion cell layer" },
        ],
    },
} as never);

function renderClasses(
    showArea: boolean,
    resolution = { x: 1000, y: 1000, z: 1 },
) {
    // 1 mm pixels by default, so each pixel is 1 mm².
    const mask = {
        version: 0,
        exportData: () => Uint8Array.from([1, 1, 2, 0]),
    };
    const ctx = layersContexts("inst-1", {
        resolution,
        getMask: () => mask,
    });
    const view = render(MultiFeatureSelector, {
        props: { segmentation: layers, active: true, showArea },
        context: ctx.context,
    });
    return { ...view, segmentationContext: ctx.segmentationContext };
}

describe("MultiFeatureSelector", () => {
    it("each class row ends with its area this slice while Area is on and the image has a resolution; the class opacity sliders are labelled and show percent", async () => {
        const { container, segmentationContext } = renderClasses(true);
        expect(
            screen.getByRole("group", { name: "Class" }),
        ).toBeInTheDocument();
        const nerve = screen
            .getByRole("radio", { name: "Nerve fibre layer" })
            .closest("li")!;
        expect(within(nerve).getByText("2.00 mm²")).toBeInTheDocument();
        const ganglion = screen
            .getByRole("radio", { name: "Ganglion cell layer" })
            .closest("li")!;
        expect(within(ganglion).getByText("1.00 mm²")).toBeInTheDocument();
        expect(screen.queryByText("Background")).toBeNull();
        expect(
            screen.getByRole("slider", { name: "Active class" }),
        ).toBeInTheDocument();
        // The stored 0.2 shows as 20 %; a typed 50 stores 0.5.
        expect(
            screen.getByRole("slider", { name: "Other classes" }),
        ).toHaveAttribute("aria-valuetext", "20%");
        const other = screen.getByRole("spinbutton", { name: "Other classes" });
        await fireEvent.input(other, { target: { value: "50" } });
        await fireEvent.change(other);
        expect(segmentationContext.multiClassInactiveAlpha).toBe(0.5);
        await expectNoAxeViolations(container);
        cleanup();

        renderClasses(false);
        expect(screen.queryByText(/mm²/)).toBeNull();
        expect(screen.queryByText("Area this slice")).toBeNull();
        cleanup();

        renderClasses(true, { x: -1, y: -1, z: -1 });
        expect(screen.queryByText(/mm²/)).toBeNull();
    });
});
