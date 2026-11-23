import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import PanelRendering from "./PanelRendering.svelte";

function viewerContext(supportsColorRenderModes: boolean, renderMode: string) {
    return {
        renderMode,
        windowLevel: { min: 0, max: 255 },
        image: { supportsColorRenderModes, orientation: "unknown" },
    };
}

function renderPanel(context: ReturnType<typeof viewerContext>) {
    return render(PanelRendering, {
        context: new Map<string, unknown>([["viewerContext", context]]),
    });
}

describe("PanelRendering", () => {
    it("lists the colour modes as radios and writes the choice back", async () => {
        const context = viewerContext(true, "Original");
        renderPanel(context);

        const group = screen.getByRole("radiogroup", { name: "Render mode" });
        expect(group.querySelectorAll("input")).toHaveLength(10);
        await fireEvent.click(screen.getByRole("radio", { name: "CLAHE" }));
        expect(context.renderMode).toBe("CLAHE");
    });

    it("falls back to Original when the mode is not available", () => {
        const context = viewerContext(false, "Sharpened");
        renderPanel(context);

        expect(screen.getAllByRole("radio")).toHaveLength(2);
        expect(context.renderMode).toBe("Original");
    });

    it("shows a select when radios are off", () => {
        render(PanelRendering, {
            props: { radio: false },
            context: new Map<string, unknown>([
                ["viewerContext", viewerContext(true, "Original")],
            ]),
        });
        expect(
            screen.getByRole("combobox", { name: "Render mode" }),
        ).toBeInTheDocument();
    });
});
