import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import Splitter from "./Splitter.svelte";
import { expectNoAxeViolations } from "./testUtils";

function renderSplitter() {
    const props = {
        axis: "col" as const,
        label: "Resize columns 1 and 2",
        controls: "slot-0 slot-1",
        valueNow: 50,
        valueMin: 20,
        valueMax: 80,
        style: "",
        ondragstart: vi.fn(),
        ondrag: vi.fn(),
        ondragend: vi.fn(),
        oncancel: vi.fn(),
        onstep: vi.fn(),
        onlimit: vi.fn(),
        onreset: vi.fn(),
    };
    const result = render(Splitter, { props });
    const separator = screen.getByRole("separator", {
        name: "Resize columns 1 and 2",
    });
    return { props, separator, ...result };
}

async function pickUp(separator: HTMLElement) {
    await fireEvent.pointerDown(separator, {
        clientX: 100,
        clientY: 0,
        pointerId: 1,
    });
    await fireEvent.pointerUp(separator, {
        clientX: 100,
        clientY: 0,
        pointerId: 1,
    });
}

describe("Splitter", () => {
    it("steps with the arrow keys along its axis only", async () => {
        // aria-controls must name elements that exist, or axe flags it.
        const viewports = ["slot-0", "slot-1"].map((id) => {
            const el = document.createElement("div");
            el.id = id;
            return el;
        });
        document.body.append(...viewports);
        const { props, separator, container } = renderSplitter();
        await fireEvent.keyDown(separator, { key: "ArrowRight" });
        await fireEvent.keyDown(separator, { key: "ArrowUp" });
        expect(props.onstep).toHaveBeenCalledTimes(1);
        expect(props.onstep).toHaveBeenCalledWith(1);
        await expectNoAxeViolations(container);
        viewports.forEach((el) => el.remove());
    });

    it("sends Home and End to the limits and Enter to the reset", async () => {
        const { props, separator } = renderSplitter();
        await fireEvent.keyDown(separator, { key: "Home" });
        await fireEvent.keyDown(separator, { key: "End" });
        await fireEvent.keyDown(separator, { key: "Enter" });
        expect(props.onlimit.mock.calls).toEqual([["min"], ["max"]]);
        expect(props.onreset).toHaveBeenCalledTimes(1);
    });

    it("drags with the pointer", async () => {
        const { props, separator } = renderSplitter();
        await fireEvent.pointerDown(separator, {
            clientX: 100,
            clientY: 0,
            pointerId: 1,
        });
        await fireEvent.pointerMove(separator, {
            clientX: 140,
            clientY: 0,
            pointerId: 1,
        });
        await fireEvent.pointerUp(separator, {
            clientX: 140,
            clientY: 0,
            pointerId: 1,
        });
        expect(props.ondragstart).toHaveBeenCalledTimes(1);
        expect(props.ondrag).toHaveBeenCalledWith(40);
        expect(props.ondragend).toHaveBeenCalled();
        expect(screen.queryByTestId("splitter-pickup")).toBeNull();
    });

    it("picks up on a click and places on the next click", async () => {
        const { props, separator } = renderSplitter();
        await pickUp(separator);
        const overlay = screen.getByTestId("splitter-pickup");
        await fireEvent.pointerMove(overlay, { clientX: 130, clientY: 0 });
        expect(props.ondrag).toHaveBeenCalledWith(30);
        await fireEvent.click(overlay);
        expect(props.ondragend).toHaveBeenCalled();
        expect(screen.queryByTestId("splitter-pickup")).toBeNull();
    });

    it.each(["Escape", "Tab", "blur"])(
        "cancels a pick-up on %s",
        async (how) => {
            const { props, separator } = renderSplitter();
            await pickUp(separator);
            if (how === "blur") await fireEvent.blur(separator);
            else await fireEvent.keyDown(separator, { key: how });
            expect(props.oncancel).toHaveBeenCalledTimes(1);
            expect(screen.queryByTestId("splitter-pickup")).toBeNull();
        },
    );
});
