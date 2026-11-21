import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
    features,
    modelSegmentations,
    segmentations,
} from "$lib/data/stores.svelte";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import { BinaryMask } from "$lib/webgl/mask.svelte";
import {
    graderSegmentation,
    layersContexts,
    ME,
    modelSegmentation,
} from "./testContexts";

// The region tool adds overlays to a real viewer, which jsdom cannot run.
vi.mock(
    "$lib/viewer-window/panelSegmentation/NewSegmentationRegion.svelte",
    () => ({ default: () => {} }),
);
vi.mock("$lib/data/api", async (original) => ({
    ...(await original<typeof import("$lib/data/api")>()),
    deleteSegmentation: vi.fn(async (id: number) => {
        segmentations.delete(id);
    }),
}));

// A slow save, so the header shows its progress in New's place while it runs.
vi.mock(
    "$lib/viewer-window/panelSegmentation/createSegmentationHelpers",
    async (original) => ({
        ...(await original<
            typeof import("$lib/viewer-window/panelSegmentation/createSegmentationHelpers")
        >()),
        createQuestionableSegmentation: vi.fn(async () => {
            await new Promise((r) => setTimeout(r, 20));
        }),
    }),
);

const { createQuestionableSegmentation } = await import(
    "$lib/viewer-window/panelSegmentation/createSegmentationHelpers"
);
const { default: SegmentationsSection } = await import(
    "./SegmentationsSection.svelte"
);

afterEach(() => {
    cleanup();
    segmentations.clear();
    modelSegmentations.clear();
    localStorage.clear();
    features.clear();
});

function seed() {
    modelSegmentations.set(11, modelSegmentation(11, "Drusen AI v2"));
    segmentations.set(1, graderSegmentation(1, ME, "Drusen v2"));
    segmentations.set(2, graderSegmentation(2, ME, "Geographic atrophy"));
    segmentations.set(3, graderSegmentation(3, 9, "Hyperreflective foci"));
}

function renderSection(
    shown = true,
    over: Parameters<typeof layersContexts>[1] = {},
) {
    const ctx = layersContexts("inst-1", over);
    const ontoggle = vi.fn();
    const view = render(SegmentationsSection, {
        props: { open: true, ontoggle, shown },
        context: ctx.context,
    });
    return { ...ctx, ontoggle, view };
}

describe("SegmentationsSection", () => {
    it("groups rows AI, Mine, then colleagues by name; AI and Mine start open", async () => {
        seed();
        const { view } = renderSection();
        expect(
            screen.getByRole("button", { name: /Segmentations\s*4/ }),
        ).toHaveAttribute("aria-expanded", "true");
        const groups = screen
            .getAllByRole("heading", { level: 4 })
            .map((h) => h.textContent?.replace(/\s+/g, " ").trim());
        expect(groups).toEqual(["AI 1", "Mine 2", "Grader 9 1"]);
        expect(
            screen.getByRole("button", { name: "Drusen AI v2" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Drusen v2" }),
        ).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Hyperreflective foci" }),
        ).toBeNull();
        await fireEvent.click(screen.getByRole("button", { name: /Grader 9/ }));
        expect(
            screen.getByRole("button", { name: "Hyperreflective foci" }),
        ).toBeInTheDocument();
        await expectNoAxeViolations(view.container);
    });

    it("while shown, open or collapsed, the viewport's segmentation tools are active, and Area hides the area lines", async () => {
        seed();
        // The BinaryMask constructor only reads the image's size and webgl shaders, so a minimal fake image will do.
        const fakeImage = {
            width: 100,
            height: 100,
            depth: 1,
            webgl: { shaders: {} },
        };
        const mask = new BinaryMask(
            fakeImage as never,
            graderSegmentation(1, ME, "x"),
        );
        mask.pixelArea = 1_000_000;
        const { viewerContext, view } = renderSection(true, {
            resolution: { x: 1, y: 1, z: 1 },
            getMask: () => mask,
        });
        expect(viewerContext.activePanels.has("Segmentation")).toBe(true);
        expect((await screen.findAllByText(/Area this slice/)).length).toBe(3);
        const area = screen.getByRole("switch", { name: "Area" });
        expect(area).toHaveAttribute("aria-checked", "true");
        await fireEvent.click(area);
        expect(screen.queryByText(/Area this slice/)).toBeNull();
        expect(localStorage.getItem("eyened:viewer:layerArea")).toBe("false");
        await view.rerender({ shown: false });
        expect(viewerContext.activePanels.has("Segmentation")).toBe(false);
        await view.rerender({ shown: true });
        expect(viewerContext.activePanels.has("Segmentation")).toBe(true);
        await view.rerender({ open: false });
        expect(viewerContext.activePanels.has("Segmentation")).toBe(true);
        view.unmount();
    });

    it("Delete asks first and removes the row on confirm", async () => {
        seed();
        renderSection();
        const row = screen.getByRole("group", {
            name: /Drusen v2 segmentation/,
        });
        await fireEvent.click(
            within(row).getByRole("button", { name: "Delete" }),
        );
        const dialog = await screen.findByRole("dialog");
        expect(
            within(dialog).getByText("Delete segmentation"),
        ).toBeInTheDocument();
        expect(within(dialog).getByText("Drusen v2 [1]")).toBeInTheDocument();
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Delete" }),
        );
        await vi.waitFor(() =>
            expect(
                screen.queryByRole("button", { name: "Drusen v2" }),
            ).toBeNull(),
        );
    });

    it("an image without segmentations says to use +, which opens New with focus in the feature combo box", async () => {
        renderSection();
        expect(
            screen.getByText("Use + to draw on this image."),
        ).toBeInTheDocument();
        expect(screen.queryByRole("switch", { name: "Area" })).toBeNull();
        await fireEvent.click(
            screen.getByRole("button", { name: "New segmentation" }),
        );
        const search = await screen.findByRole("combobox", {
            name: "Feature",
        });
        await vi.waitFor(() => expect(search).toHaveFocus());
        expect(
            screen.getByRole("button", { name: "Advanced…" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Region box…" }),
        ).toBeInTheDocument();
    });

    it("Advanced: Multi-class drops a feature without subfeatures, offers only those with, and locks Placement to Full image", async () => {
        features.set(1, {
            id: 1,
            name: "Artery / vein",
            subfeatures: [{ id: 2, name: "Artery" }],
        } as never);
        features.set(3, { id: 3, name: "Drusen" } as never);
        renderSection();
        await fireEvent.click(
            screen.getByRole("button", { name: "New segmentation" }),
        );
        await fireEvent.click(
            await screen.findByRole("button", { name: "Advanced…" }),
        );
        const dialog = await screen.findByRole("dialog", {
            name: "New segmentation",
        });
        const feature = within(dialog).getByRole("combobox", {
            name: "Feature",
        });
        await fireEvent.input(feature, { target: { value: "Dru" } });
        await screen.findByRole("option", { name: "Drusen" });
        await fireEvent.keyDown(feature, { key: "ArrowDown" });
        await fireEvent.keyDown(feature, { key: "Enter" });
        expect(feature).toHaveValue("Drusen");
        await fireEvent.click(
            within(dialog).getByRole("radio", { name: "Region box" }),
        );

        await fireEvent.click(
            within(dialog).getByRole("radio", { name: "Multi-class" }),
        );

        expect(feature).toHaveValue("");
        const full = within(dialog).getByRole("radio", { name: "Full image" });
        expect(full).toBeChecked();
        expect(full).toBeDisabled();
        expect(
            within(dialog).getByRole("radio", { name: "Region box" }),
        ).toBeDisabled();
        await fireEvent.input(feature, { target: { value: "r" } });
        expect(
            await screen.findByRole("option", { name: "Artery / vein" }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("option", { name: "Drusen" })).toBeNull();
    });

    it("closing the popover returns focus to New", async () => {
        renderSection();
        await fireEvent.click(
            screen.getByRole("button", { name: "New segmentation" }),
        );
        const search = await screen.findByRole("combobox", {
            name: "Feature",
        });
        await vi.waitFor(() => expect(search).toHaveFocus());
        await fireEvent.keyDown(search, { key: "Escape" });
        await vi.waitFor(() =>
            expect(
                screen.queryByRole("combobox", {
                    name: "Feature",
                }),
            ).toBeNull(),
        );
        const header = screen.getByRole("button", { name: "New segmentation" });
        await vi.waitFor(() => expect(header).toHaveFocus());
    });

    it("picking a feature leaves focus on New", async () => {
        features.set(5, { id: 5, name: "Drusen" } as never);
        renderSection();
        await fireEvent.click(
            screen.getByRole("button", { name: "New segmentation" }),
        );
        const search = await screen.findByRole("combobox", {
            name: "Feature",
        });
        await fireEvent.input(search, { target: { value: "Dru" } });
        await screen.findByRole("option", { name: "Drusen" });
        await fireEvent.keyDown(search, { key: "ArrowDown" });
        await fireEvent.keyDown(search, { key: "Enter" });
        await vi.mocked(createQuestionableSegmentation).mock.results[0]!.value;
        // New is replaced by the progress while the save runs, so look the button up again.
        await vi.waitFor(() =>
            expect(
                screen.getByRole("button", { name: "New segmentation" }),
            ).toHaveFocus(),
        );
    });
});
