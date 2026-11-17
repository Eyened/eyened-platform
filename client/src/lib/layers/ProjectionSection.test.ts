import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { segmentations } from "$lib/data/stores.svelte";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import ProjectionSection from "./ProjectionSection.svelte";
import { graderSegmentation, layersContexts, ME } from "./testContexts";

afterEach(() => {
    cleanup();
    segmentations.clear();
});

/** A linked OCT row whose projection comes from `from`, or from no viewport. */
function row(octPublicId: string, from?: unknown) {
    return {
        octPublicId,
        identityMapping: false,
        mode: "off",
        manager: { octImage: { depth: 49 }, source: from },
    } as never;
}

describe("ProjectionSection", () => {
    it("names the source viewport with its shown segmentations and opacity, or says there is nothing to project", async () => {
        const oct = layersContexts("oct-1", { is3D: true });
        oct.mainViewerContext.alpha = 0.6;
        segmentations.set(
            1,
            graderSegmentation(1, ME, "Drusen", { image_id: "oct-1" } as never),
        );
        const from = {
            mainViewerContext: oct.mainViewerContext,
            position: () => 2,
        };
        const { container } = render(ProjectionSection, {
            props: {
                sources: [row("oct-1", from), row("oct-2")],
                open: true,
                ontoggle: vi.fn(),
            },
            context: layersContexts("faf-1").context,
        });
        // A count here would read as projections painted; it only ever counted OCTs.
        screen.getByRole("button", { name: "En-face projection" });
        expect(
            screen.getByText("From viewport 3: no segmentations shown"),
        ).toBeInTheDocument();
        oct.segmentationContext.shownSegmentations.add("grader_segmentation_1");
        expect(
            await screen.findByText(
                "From viewport 3: 1 segmentation, opacity 60 %",
            ),
        ).toBeInTheDocument();
        expect(
            screen.getByText(
                "Not open in a viewport. Drag its tile into one to project it.",
            ),
        ).toBeInTheDocument();
        // Each switcher is named and points at its own helper line.
        await expectNoAxeViolations(container);
    });
});
