import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { Line } from "../distanceLines.svelte";
import { layersContexts } from "../testContexts";

const { default: LinePane } = await import("./LinePane.svelte");

afterEach(cleanup);

describe("LinePane", () => {
    it("numbers the line among its own B-scan's lines after the viewer moves to another B-scan", () => {
        const { distance, viewerContext, context } = layersContexts("inst-1");
        const line = new Line({ x: 0, y: 0 }, { x: 3, y: 4 }, 0);
        distance.add(line);
        // The viewer has scrolled to B-scan 1; the selection stays on the line.
        viewerContext.index = 1;
        render(LinePane, {
            props: { id: "pane-name", line, lines: distance, scale: null },
            context,
        });
        expect(
            screen.getByRole("heading", { name: "Line 1" }),
        ).toBeInTheDocument();
    });
});
