import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { formAnnotations } from "$lib/data/stores.svelte";
import { fakeImage, layersContexts, reg } from "../testContexts";
import PointsetPane from "./PointsetPane.svelte";

const pt = { x: 1, y: 2 };

afterEach(() => {
    cleanup();
    formAnnotations.clear();
});

function renderPane(images = [fakeImage("inst-2")]) {
    const ctx = layersContexts("inst-1", { images });
    render(PointsetPane, {
        props: { id: "pane-name", pointsetId: 12 },
        context: ctx.context,
    });
    return ctx;
}

describe("PointsetPane", () => {
    it("the pane shows the pointset's save state and its points per image", async () => {
        reg(12, 9, { "inst-1": [pt, pt, pt], "inst-2": [pt, pt, null] });
        const { win } = renderPane();
        expect(screen.getByText("This CF · 2022-05-10")).toBeInTheDocument();
        expect(screen.getByText("2 · no 3")).toBeInTheDocument();
        win.pointsets.sync.set(12, "error");
        expect(await screen.findByText("Couldn't save")).toBeInTheDocument();
    });

    it("numbers a retake of this image by the window's strip order: this image is the first, the other line reads #2", () => {
        reg(12, 9, { "inst-1": [pt], "inst-2": [pt] });
        renderPane([
            fakeImage("inst-2", {
                modality: "ColorFundus",
                date: "2022-05-10",
                device: { manufacturer: "Topcon", model: "Maestro2" },
            }),
        ]);
        expect(screen.getByText("This CF · 2022-05-10")).toBeInTheDocument();
        expect(screen.getByText("CF · 2022-05-10 #2")).toBeInTheDocument();
        expect(screen.getAllByText("Topcon Maestro2")).toHaveLength(2);
    });
});
