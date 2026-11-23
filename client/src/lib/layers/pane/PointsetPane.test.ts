import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import { formAnnotations } from "$lib/data/stores.svelte";
import {
    formAnnotationSaver,
    formAnnotationSavers,
} from "$lib/saving/formAnnotationSavers";
import { fakeImage, layersContexts, ME, reg } from "../testContexts";
import PointsetPane from "./PointsetPane.svelte";

const pt = { x: 1, y: 2 };

afterEach(() => {
    cleanup();
    formAnnotations.clear();
    formAnnotationSavers.clear();
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
    it("the pane shows the pointset's save state and its points per image; a failed save has Retry", async () => {
        reg(12, 9, { "inst-1": [pt, pt, pt], "inst-2": [pt, pt, null] });
        renderPane();
        expect(screen.getByText("This CF · 2022-05-10")).toBeInTheDocument();
        expect(screen.getByText("2 · no 3")).toBeInTheDocument();
        formAnnotationSaver(12, "registration", {
            to: "focus",
            focus: () => {},
        }).state = "error";
        expect(await screen.findByText("Couldn't save")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Retry" }),
        ).toBeInTheDocument();
    });

    it("Edit with arms Point", async () => {
        reg(12, ME, { "inst-1": [pt] });
        const ctx = layersContexts("inst-1", { images: [fakeImage("inst-2")] });
        render(PointsetPane, {
            props: {
                id: "pane-name",
                pointsetId: 12,
                remove: createRawSnippet(() => ({
                    render: () => "<span></span>",
                })),
            },
            context: ctx.context,
        });
        const group = screen.getByRole("group", { name: "Edit with" });
        await fireEvent.click(
            within(group).getByRole("button", { name: "Point" }),
        );
        expect(ctx.workspace.arm).toHaveBeenCalledWith("point");
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
