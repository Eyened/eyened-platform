import { fireEvent, render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import { viewerOf, type ImageKind } from "./testViewer";
import SliceScrollbar from "./SliceScrollbar.svelte";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

const WIDTHS: Record<string, number> = {
    numbers: 200,
    count: 60,
    word: 50,
    readout: 60,
};

async function renderEdge(
    kind: ImageKind,
    { scans = [], width = 2000 }: { scans?: number[]; width?: number } = {},
) {
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(
        function (this: HTMLElement) {
            return WIDTHS[this.dataset.part ?? ""] ?? 0;
        },
    );
    const viewerContext = viewerOf(kind);
    viewerContext.index = 64;
    viewerContext.viewerSize = { width, height: 500 };
    const result = render(SliceScrollbar, {
        context: new Map<string, unknown>([
            ["viewerContext", viewerContext],
            [
                "mainViewerContext",
                { segmentationContext: { scan_indices: scans } },
            ],
        ]),
    });
    await tick();
    return { ...result, viewerContext };
}

const line = (c: Element) => c.querySelector(".line") as HTMLElement;
const visible = (c: Element) => {
    const copy = line(c).cloneNode(true) as HTMLElement;
    copy.querySelector(".measure")?.remove();
    return copy.textContent?.replace(/\s+/g, " ").trim();
};

describe("SliceScrollbar", () => {
    afterEach(() => vi.restoreAllMocks());

    it("reads out 1-based while the stored index stays 0-based", async () => {
        const { container, viewerContext } = await renderEdge("bscan");
        expect(visible(container)).toBe("B-scan 65 / 128");
        expect(viewerContext.index).toBe(64);
        const slider = screen.getByRole("slider", { name: "Slice" });
        expect(slider).toHaveAttribute("aria-valuetext", "B-scan 65 of 128");
        await expectNoAxeViolations(container);
    });

    it("announces a slice with data", async () => {
        await renderEdge("bscan", { scans: [64] });
        expect(screen.getByRole("slider", { name: "Slice" })).toHaveAttribute(
            "aria-valuetext",
            "B-scan 65 of 128, has segmentation",
        );
    });

    it("steps with the arrows, top to bottom, while Lock is on", async () => {
        const { viewerContext } = await renderEdge("bscan");
        viewerContext.lockScroll = true;
        await tick();
        const slider = screen.getByRole("slider", { name: "Slice" });
        await fireEvent.keyDown(slider, { key: "ArrowDown" });
        expect(viewerContext.index).toBe(65);
        await tick();
        await fireEvent.keyDown(slider, { key: "ArrowUp" });
        expect(viewerContext.index).toBe(64);
        await tick();
        await fireEvent.keyDown(slider, { key: "End" });
        expect(viewerContext.index).toBe(127);
    });

    it("Lock sets the image's lock and is not pressed by a drawing tool", async () => {
        const { viewerContext } = await renderEdge("bscan");
        viewerContext.lockScroll = true;
        await tick();
        const lock = screen.getByRole("button", { name: "Lock slice" });
        expect(lock).toHaveAttribute("aria-pressed", "false");
        await fireEvent.click(lock);
        expect(viewerContext.sliceLocked).toBe(true);
    });

    it("a press on a tick goes to its slice and the track does not move there too", async () => {
        const { container, viewerContext } = await renderEdge("bscan", {
            scans: [10],
        });
        const track = container.querySelector(".track") as HTMLElement;
        vi.spyOn(track, "getBoundingClientRect").mockReturnValue(
            new DOMRect(0, 0, 14, 127),
        );
        const slider = track.querySelector("[data-slider-root]") as HTMLElement;
        await fireEvent.pointerDown(slider, { button: 0, clientY: 10 });
        expect(viewerContext.index).toBe(10);
        expect(document.activeElement).not.toBe(
            screen.getByRole("slider", { name: "Slice" }),
        );
    });

    it("shows the number line 1-based and jumps with one click, past Lock", async () => {
        const { container, viewerContext } = await renderEdge("bscan", {
            scans: [3, 64],
        });
        viewerContext.lockScroll = true;
        expect(visible(container)).toContain("B-scan 65 / 128");
        const button = screen.getByRole("button", { name: "Go to B-scan 4" });
        expect(button).toHaveAttribute("tabindex", "-1");
        expect(
            screen.getByRole("button", { name: "Go to B-scan 65" }),
        ).toHaveAttribute("aria-current", "true");
        await fireEvent.click(button);
        expect(viewerContext.index).toBe(3);
    });

    it("windows more than 12 annotated slices and counts them", async () => {
        const scans = Array.from({ length: 23 }, (_, i) => i * 5);
        const { container } = await renderEdge("bscan", { scans });
        expect(visible(container)).toContain("23 with data");
        const numbers = [...container.querySelectorAll(".numbers > *")].map(
            (n) => n.textContent?.trim(),
        );
        expect(numbers).toEqual([
            "1",
            "…",
            "41",
            "46",
            "51",
            "56",
            "61",
            "66",
            "71",
            "76",
            "81",
            "…",
            "111",
        ]);
    });

    it("hides the number line when it does not fit, and keeps the ticks", async () => {
        const { container } = await renderEdge("bscan", {
            scans: [3, 64],
            width: 300,
        });
        expect(visible(container)).toBe("B-scan 65 / 128");
        expect(
            screen.queryByRole("button", { name: "Go to B-scan 4" }),
        ).toBeNull();
        expect(container.querySelectorAll(".tick")).toHaveLength(2);
    });

    it("rounds a pointer between slices without writing it back", async () => {
        const { container, viewerContext } = await renderEdge("bscan");
        const setIndex = vi.spyOn(viewerContext, "setIndex");
        viewerContext.index = 64.4;
        await tick();
        await tick();
        expect(visible(container)).toBe("B-scan 65 / 128");
        expect(setIndex).not.toHaveBeenCalled();
    });

    it("returns focus to the image after a mouse drag, not after a key", async () => {
        const { viewerContext } = await renderEdge("bscan");
        const image = document.createElement("div");
        image.tabIndex = 0;
        image.append(viewerContext.canvas2D);
        document.body.append(image);
        const slider = screen.getByRole("slider", { name: "Slice" });

        slider.focus();
        await fireEvent.keyDown(slider, { key: "ArrowDown" });
        expect(document.activeElement).toBe(slider);

        await fireEvent.pointerDown(slider, { button: 0 });
        await fireEvent.pointerUp(slider);
        expect(document.activeElement).toBe(image);
        image.remove();
    });
});
