import {
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import { viewerOf, type ImageKind } from "./testViewer";
import ViewControls from "./ViewControls.svelte";
import type { ViewerContext } from "./viewerContext.svelte";

vi.mock("$lib/webgl/imageRenderer", () => ({ BaseImageRenderer: class {} }));

const FULL = 620;
const COMPACT = 380;

/** Renders the bar in a viewport `width` px wide; jsdom has no layout, so the measured widths are mocked. */
async function renderBar(
    kind: ImageKind,
    width: number,
    change?: (v: ViewerContext) => void,
) {
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(
        width,
    );
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(
        function (this: HTMLElement) {
            return this.dataset.row === "full" ? FULL : COMPACT;
        },
    );
    const viewerContext = viewerOf(kind);
    change?.(viewerContext);
    const result = render(ViewControls, {
        context: new Map([["viewerContext", viewerContext]]),
    });
    await tick();
    return { ...result, viewerContext };
}

const bar = () => screen.getByRole("group", { name: "View controls" });

describe("ViewControls", () => {
    afterEach(() => vi.restoreAllMocks());

    it("shows mode and W/L on 2D images, with no stretch", async () => {
        const { container } = await renderBar("grey", 1000);
        const controls = within(bar());
        expect(
            controls.getByRole("button", { name: /Render mode/ }),
        ).toBeInTheDocument();
        expect(
            controls.getByRole("slider", { name: "Window low" }),
        ).toBeInTheDocument();
        expect(
            controls.getByRole("slider", { name: "Window high" }),
        ).toBeInTheDocument();
        expect(controls.queryByRole("group", { name: "Stretch" })).toBeNull();
        expect(controls.queryByRole("button", { name: /Stretch/ })).toBeNull();
        await expectNoAxeViolations(container);
    });

    it("shows presets and slider inline on a B-scan when the full bar fits", async () => {
        const { container } = await renderBar("bscan", FULL);
        expect(
            within(bar()).getByRole("slider", { name: "Stretch" }),
        ).toBeInTheDocument();
        expect(
            within(bar()).getByRole("radio", { name: "Stretch 8×" }),
        ).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("moves stretch to a popover at compact width, and refits on a preset", async () => {
        const { viewerContext } = await renderBar("bscan", FULL - 1, (v) => {
            v.stretch = 3.5;
        });
        const init = vi.spyOn(viewerContext, "initTransform");
        expect(
            within(bar()).queryByRole("radio", { name: "Stretch 8×" }),
        ).toBeNull();
        await fireEvent.click(
            within(bar()).getByRole("button", { name: "Stretch 3.5×" }),
        );
        const preset8 = await screen.findByRole("radio", {
            name: "Stretch 8×",
        });
        expect(
            screen
                .getAllByRole("radio")
                .filter((r) => r.getAttribute("aria-checked") === "true"),
        ).toEqual([]);
        await fireEvent.click(preset8);
        expect(viewerContext.stretch).toBe(8);
        expect(init).toHaveBeenCalledOnce();
        expect(preset8).toHaveAttribute("aria-checked", "true");
    });

    it("keeps a preset selected when pressed again", async () => {
        const { viewerContext } = await renderBar("bscan", FULL, (v) => {
            v.stretch = 8;
        });
        const preset8 = screen.getByRole("radio", { name: "Stretch 8×" });
        await fireEvent.click(preset8);
        expect(viewerContext.stretch).toBe(8);
        expect(preset8).toHaveAttribute("aria-checked", "true");
    });

    it("does not write the image's default stretch back through the slider", async () => {
        const { viewerContext } = await renderBar("bscan", FULL);
        await tick();
        expect(viewerContext.stretch).toBe(viewerContext.defaultStretch);
    });

    it("folds to View with a label of non-defaults only", async () => {
        await renderBar("bscan", COMPACT - 1);
        expect(
            within(bar()).getByRole("button", { name: "View" }),
        ).toBeInTheDocument();
        expect(within(bar()).queryByRole("slider")).toBeNull();
        expect(bar().textContent?.trim()).toBe("View");
    });

    it("names the non-default settings on the folded bar", async () => {
        await renderBar("bscan", COMPACT - 1, (v) => {
            v.renderMode = "CLAHE";
            v.stretch = 2;
        });
        expect(bar()).toHaveTextContent("CLAHE · 2×");
    });

    it("falls back to Original when the mode is not available", async () => {
        const { viewerContext } = await renderBar("grey", 1000, (v) => {
            v.renderMode = "Sharpened";
        });
        await tick();
        expect(viewerContext.renderMode).toBe("Original");
    });

    it("lists a colour image's modes, each with its key", async () => {
        const { viewerContext } = await renderBar("colour", 1000);
        const trigger = within(bar()).getByRole("button", {
            name: /Render mode/,
        });
        await fireEvent.keyDown(trigger, { key: "Enter" });
        const options = await screen.findAllByRole("option");
        expect(options[0]).toHaveTextContent("Original R");
        const sharpened = options.find((o) =>
            o.textContent?.includes("Sharpened"),
        )!;
        await fireEvent.pointerUp(sharpened, {
            button: 0,
            pointerType: "mouse",
        });
        await waitFor(() => expect(viewerContext.renderMode).toBe("Sharpened"));
    });

    it("moves W/L from the keyboard", async () => {
        const { viewerContext } = await renderBar("grey", 1000);
        await fireEvent.keyDown(
            screen.getByRole("slider", { name: "Window low" }),
            { key: "ArrowRight" },
        );
        expect(viewerContext.windowLevel).toEqual({ min: 1, max: 255 });
    });

    it("returns focus to the image after a mouse drag on W/L, not after a key", async () => {
        const { viewerContext } = await renderBar("grey", 1000);
        const image = document.createElement("div");
        image.tabIndex = 0;
        image.append(viewerContext.canvas2D);
        document.body.append(image);
        const low = screen.getByRole("slider", { name: "Window low" });

        // jsdom has no focus heuristics, so :focus-visible is set by hand.
        const focusVisible = vi.spyOn(low, "matches").mockReturnValue(true);
        low.focus();
        await fireEvent.keyDown(low, { key: "ArrowRight" });
        expect(document.activeElement).toBe(low);

        focusVisible.mockReturnValue(false);
        await fireEvent.pointerDown(low, { button: 0 });
        await fireEvent.pointerUp(low);
        expect(document.activeElement).toBe(image);
        image.remove();
    });

    describe("render mode focus", () => {
        async function pick(name: string, mouse: boolean) {
            const { viewerContext } = await renderBar("colour", 1000);
            const image = document.createElement("div");
            image.tabIndex = 0;
            image.append(viewerContext.canvas2D);
            document.body.append(image);
            const trigger = within(bar()).getByRole("button", {
                name: /Render mode/,
            });
            // jsdom has no focus heuristics, so :focus-visible is set by hand.
            vi.spyOn(trigger, "matches").mockReturnValue(!mouse);
            trigger.focus();
            await fireEvent.keyDown(trigger, { key: "Enter" });
            const options = await screen.findAllByRole("option");
            const option = options.find((o) =>
                o.textContent?.startsWith(name),
            )!;
            await fireEvent.pointerUp(option, {
                button: 0,
                pointerType: "mouse",
            });
            await waitFor(() =>
                expect(screen.queryByRole("listbox")).toBeNull(),
            );
            return { image, trigger };
        }

        it("moves focus to the image after a mouse pick", async () => {
            const { image } = await pick("CLAHE", true);
            expect(document.activeElement).toBe(image);
            image.remove();
        });

        it("moves focus to the image when the current mode is picked again", async () => {
            const { image } = await pick("Original", true);
            expect(document.activeElement).toBe(image);
            image.remove();
        });

        it("keeps focus on the trigger after a keyboard pick", async () => {
            const { image, trigger } = await pick("CLAHE", false);
            expect(document.activeElement).toBe(trigger);
            image.remove();
        });
    });
});
