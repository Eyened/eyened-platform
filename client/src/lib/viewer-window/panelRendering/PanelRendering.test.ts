import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import PanelRendering from "./PanelRendering.svelte";

function viewerContext(
    supportsColorRenderModes: boolean,
    renderMode: string,
    extras: Record<string, unknown> = {},
) {
    return {
        renderMode,
        angioDisplayMode: "structural",
        windowLevel: { min: 0, max: 255 },
        image: {
            supportsColorRenderModes,
            orientation: "unknown",
            hasFlow: false,
            instance: { id: "img-1" },
        },
        ...extras,
    };
}

function renderPanel(context: ReturnType<typeof viewerContext>) {
    return render(PanelRendering, {
        context: new Map<string, unknown>([
            ["viewerContext", context],
            [
                "viewerWindowContext",
                { octaFlowReady: new Map<string, boolean>() },
            ],
        ]),
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
                [
                    "viewerWindowContext",
                    { octaFlowReady: new Map<string, boolean>() },
                ],
            ]),
        });
        expect(
            screen.getByRole("combobox", { name: "Render mode" }),
        ).toBeInTheDocument();
    });

    it("hides angio display radios when the image has no flow volume", () => {
        renderPanel(viewerContext(false, "Original"));
        expect(
            screen.queryByRole("radiogroup", { name: "Angio display" }),
        ).not.toBeInTheDocument();
    });

    it("shows angio display radios and binds angioDisplayMode when hasFlow", async () => {
        const context = viewerContext(false, "Original", {
            image: {
                supportsColorRenderModes: false,
                orientation: "axial",
                hasFlow: true,
                instance: { id: "img-1" },
            },
            stretch: 1,
            initTransform: () => {},
        });
        renderPanel(context);

        const group = screen.getByRole("radiogroup", { name: "Angio display" });
        expect(group.querySelectorAll("input")).toHaveLength(3);
        await fireEvent.click(
            screen.getByRole("radio", { name: "Angio flow" }),
        );
        expect(context.angioDisplayMode).toBe("flow");
        await fireEvent.click(
            screen.getByRole("radio", { name: "Flow overlay (red)" }),
        );
        expect(context.angioDisplayMode).toBe("overlay");
    });
});
