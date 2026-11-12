import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { modelSegmentations, segmentations } from "$lib/data/stores.svelte";
import {
    graderSegmentation,
    layersContexts,
    ME,
    modelSegmentation,
} from "$lib/layers/testContexts";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import ImportPanel from "./ImportPanel.svelte";

afterEach(() => {
    cleanup();
    segmentations.clear();
    modelSegmentations.clear();
});

describe("ImportPanel", () => {
    it("lists this image's convertible segmentations but not the row itself; Import stays disabled until one is picked", async () => {
        const target = graderSegmentation(1, ME, "Drusen", {
            data_representation: "Binary",
        });
        segmentations.set(1, target);
        segmentations.set(
            2,
            graderSegmentation(2, 9, "Hyperreflective foci", {
                data_representation: "Binary",
            }),
        );
        segmentations.set(
            3,
            graderSegmentation(3, ME, "Retinal layers", {
                data_representation: "MultiClass",
            }),
        );
        modelSegmentations.set(10, modelSegmentation(10, "Geographic atrophy"));
        const mask = { exportData: () => new Uint8Array(4) };
        const ctx = layersContexts("inst-1", { getMask: () => mask });
        const segmentationItem =
            ctx.segmentationContext.getSegmentationItem(target);
        render(ImportPanel, {
            props: {
                segmentation: target,
                image: ctx.viewerContext.image as never,
                segmentationItem,
            },
            context: ctx.context,
        });

        await fireEvent.click(screen.getByRole("button", { name: "Import…" }));
        const dialog = await screen.findByRole("dialog", {
            name: "Import into this image",
        });
        // The first radio takes focus, not the scrolling body.
        await vi.waitFor(() =>
            expect(document.activeElement).toBe(
                within(dialog).getByRole("radio", {
                    name: "Geographic atrophy [10]",
                }),
            ),
        );
        // Each radio's (visually hidden) label is "{feature name} [{id}]".
        const names = within(dialog)
            .getAllByRole("radio")
            .map((r) => (r as HTMLInputElement).labels![0].textContent);
        expect(names).toEqual([
            "Geographic atrophy [10]",
            "Hyperreflective foci [2]",
        ]);
        const importButton = within(dialog).getByRole("button", {
            name: "Import",
        });
        expect(importButton).toHaveAttribute("aria-disabled", "true");

        await fireEvent.click(
            within(dialog).getByRole("radio", {
                name: "Hyperreflective foci [2]",
            }),
        );
        expect(importButton).not.toHaveAttribute("aria-disabled");
        await fireEvent.click(importButton);
        // The import first waits for the picked segmentation's load.
        await vi.waitFor(() =>
            expect(segmentationItem.importOther).toHaveBeenCalledWith(0, mask),
        );
        await expectNoAxeViolations(dialog);
    });
});
