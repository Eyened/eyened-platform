import { describe, it, expect, vi } from "vitest";
import type { TaskConfig } from "./taskConfigLayout";

vi.mock("./panelInfo/panelInfo.svelte", () => ({ default: {} }));
vi.mock("./panelRendering/PanelRendering.svelte", () => ({ default: {} }));
vi.mock("./panelETRDS/PanelETDRS.svelte", () => ({ default: {} }));
vi.mock("./panelRegistration/PanelRegistration.svelte", () => ({ default: {} }));
vi.mock("./panelMeasure/PanelMeasure.svelte", () => ({ default: {} }));
vi.mock("./panelForm/PanelForm.svelte", () => ({ default: {} }));
vi.mock("./panelSegmentation/PanelSegmentation.svelte", () => ({ default: {} }));
vi.mock("./panelQuickForm/PanelQuickForm.svelte", () => ({ default: {} }));
vi.mock("./icons/icons", () => ({
    Info: {},
    Rendering: {},
    ETDRS: {},
    Registration: {},
    Form: {},
    Draw: {},
}));
vi.mock("./icons/Measure.svelte", () => ({ default: {} }));
vi.mock("./panelHelp/InfoPanelHelp.svelte", () => ({ default: {} }));
vi.mock("./panelHelp/RenderingPanelHelp.svelte", () => ({ default: {} }));
vi.mock("./panelHelp/EtdrsPanelHelp.svelte", () => ({ default: {} }));
vi.mock("./panelHelp/RegistrationPanelHelp.svelte", () => ({ default: {} }));
vi.mock("./panelHelp/MeasurePanelHelp.svelte", () => ({ default: {} }));
vi.mock("./panelHelp/FormPanelHelp.svelte", () => ({ default: {} }));
vi.mock("./panelHelp/SegmentationPanelHelp.svelte", () => ({ default: {} }));

const { resolvePanels } = await import("./resolvePanels");

const baseInput = {
    is2D: true,
    etdrsSchema: undefined,
    registrationSchema: undefined,
};

describe("resolvePanels", () => {
    it("returns default panels when taskConfig has no layout", () => {
        const { panels, expandedPanelNames } = resolvePanels(baseInput, {});
        expect(panels.map((p) => p.name)).toEqual([
            "Info",
            "Rendering",
            "Measure",
            "Form",
            "Segmentation",
        ]);
        expect(expandedPanelNames).toEqual([]);
    });

    it("hides panels listed in layout.hide", () => {
        const taskConfig: TaskConfig = {
            layout: { hide: ["Form"] },
        };
        const { panels } = resolvePanels(baseInput, taskConfig);
        expect(panels.map((p) => p.name)).not.toContain("Form");
    });

    it("prepends quick-form panel and marks it expanded", () => {
        const taskConfig: TaskConfig = {
            form_schema_name: "Naevi grading",
            layout: {
                hide: ["Form"],
                prepend: [
                    { type: "quick-form", title: "Grading", expanded: true },
                ],
            },
        };
        const { panels, expandedPanelNames } = resolvePanels(
            baseInput,
            taskConfig,
        );
        expect(panels[0].name).toBe("Grading");
        expect(panels.map((p) => p.name)).not.toContain("Form");
        expect(expandedPanelNames).toEqual(["Grading"]);
    });

    it("skips unknown prepend types with a console warning", () => {
        const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
        const taskConfig = {
            layout: {
                prepend: [{ type: "unknown", title: "X" }],
            },
        } as unknown as TaskConfig;

        const { panels } = resolvePanels(baseInput, taskConfig);
        expect(panels.map((p) => p.name)).not.toContain("X");
        expect(warn).toHaveBeenCalled();
        warn.mockRestore();
    });
});
