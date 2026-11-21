import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import {
    formAnnotations,
    formSchemasByName,
    segmentations,
} from "$lib/data/stores.svelte";
import { Line } from "./distanceLines.svelte";
import { workspaceWith } from "$lib/workspace/testUtils";
import type { Workspace } from "$lib/workspace/workspace.svelte";
import type { PhotoLocator } from "$lib/registration/photoLocators";
import { LocalizerLines } from "./localizerLines.svelte";
import { graderSegmentation, layersContexts, ME } from "./testContexts";

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

const { default: LayersPanel } = await import("./LayersPanel.svelte");

afterEach(() => {
    cleanup();
    segmentations.clear();
    formAnnotations.clear();
    formSchemasByName.delete(BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID);
    localStorage.clear();
});

function attach(
    ws: Workspace,
    position: number,
    instanceId: string,
    extra: object = {},
) {
    const ctx = layersContexts(instanceId);
    ws.attachViewport(position, {
        zoomPercent: 100,
        zoomBy: vi.fn(),
        reset: vi.fn(),
        layers: {
            viewerContext: ctx.viewerContext as never,
            mainViewerContext: ctx.mainViewerContext as never,
            selection: ctx.selection,
            grids: ctx.grids,
            scale: null,
            distance: ctx.distance,
            projectionSources: [],
            localizer: new LocalizerLines(() => []),
            pointTarget: { id: null, canEdit: false, reason: null },
            drawTarget: { name: null, color: null, reason: null },
            etdrsTarget: { name: null, reason: null },
            etdrsTool: undefined,
            pointTool: undefined,
            blend: {} as never,
            ...extra,
        },
    });
    return ctx;
}

function renderPanel(ws: Workspace, hide: string[] = []) {
    const ctx = layersContexts();
    const context = new Map(ctx.context);
    context.set("workspace", ws);
    context.set("taskContext", {
        task: { task_definition: { config: { layout: { hide } } } },
    });
    return render(LayersPanel, {
        props: { subtitle: "Viewport 1 · test", shown: true },
        context,
    });
}

describe("LayersPanel", () => {
    it("lists the selected viewport's segmentations and follows the selection", async () => {
        segmentations.set(
            1,
            graderSegmentation(1, ME, "Drusen v2", {
                image_id: "inst-a",
            } as never),
        );
        segmentations.set(
            2,
            graderSegmentation(2, ME, "Geographic atrophy", {
                image_id: "inst-b",
            } as never),
        );
        const ws = workspaceWith(2);
        attach(ws, 0, "inst-a");
        attach(ws, 1, "inst-b");
        renderPanel(ws);
        expect(
            screen.getByRole("button", { name: "Drusen v2" }),
        ).toBeInTheDocument();
        ws.select(1);
        expect(
            await screen.findByRole("button", { name: "Geographic atrophy" }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Drusen v2" })).toBeNull();
    });

    it("says No layers for a slot with no image and when the task hides every section", () => {
        const ws = workspaceWith(1, { layout: "2x1" });
        attach(ws, 0, "inst-a");
        ws.select(1);
        const first = renderPanel(ws);
        expect(screen.getByText("No layers")).toBeInTheDocument();
        first.unmount();
        ws.select(0);
        renderPanel(ws, ["Segmentation", "ETDRS", "Registration", "Measure"]);
        expect(screen.getByText("No layers")).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: /Segmentations/ }),
        ).toBeNull();
    });

    it("does not say No layers while the slot's image is still loading", () => {
        renderPanel(workspaceWith(1));
        expect(screen.queryByText("No layers")).toBeNull();
    });

    it("keeps a viewport's grids, current grid and lines while another is selected", async () => {
        const name = BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID;
        formSchemasByName.set(name, { id: 3, name } as never);
        formAnnotations.set(11, {
            id: 11,
            form_schema_id: 3,
            image_id: "inst-a",
            annotation_type: "grader_form",
            sub_task_id: null,
            creator: { id: ME, name: `Grader ${ME}` },
            form_data: {},
        } as never);
        const ws = workspaceWith(2);
        const a = attach(ws, 0, "inst-a");
        attach(ws, 1, "inst-b");
        a.distance.add(new Line({ x: 0, y: 0 }, { x: 3, y: 4 }, 0));
        renderPanel(ws);
        await fireEvent.click(
            screen.getByRole("button", { name: "ETDRS grids 1" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "Distance lines 1" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "ETDRS grid, Grader 5" }),
        );

        ws.select(1);
        await tick();
        expect(screen.queryByRole("button", { name: "Line 1" })).toBeNull();
        ws.select(0);

        expect(
            await screen.findByRole("button", { name: "ETDRS grid, Grader 5" }),
        ).toHaveAttribute("aria-pressed", "true");
        expect(
            screen.getByRole("button", { name: "Line 1" }),
        ).toBeInTheDocument();
    });

    it("Layers holds the object types and Display the view settings; no Display tab when nothing goes there", async () => {
        const ws = workspaceWith(2);
        attach(ws, 0, "inst-a");
        attach(ws, 1, "inst-b", {
            localizer: new LocalizerLines(() => [
                { octImageId: "oct-1" } as PhotoLocator,
            ]),
        });
        renderPanel(ws);
        expect(screen.getByRole("tab", { name: "Layers" })).toHaveAttribute(
            "aria-selected",
            "true",
        );
        expect(screen.queryByRole("tab", { name: "Display" })).toBeNull();

        ws.select(1);
        const display = await screen.findByRole("tab", { name: "Display" });
        expect(
            screen.getByRole("button", { name: /^Distance lines/ }),
        ).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Localizer lines" }),
        ).toBeNull();
        await fireEvent.click(display);
        expect(
            await screen.findByRole("button", { name: "Localizer lines" }),
        ).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: /^Distance lines/ }),
        ).toBeNull();
    });

    it("the pane says what to do with nothing selected; a row click names the item in the pane's region", async () => {
        segmentations.set(
            1,
            graderSegmentation(1, ME, "Drusen v2", {
                image_id: "inst-a",
            } as never),
        );
        const ws = workspaceWith(1);
        attach(ws, 0, "inst-a");
        renderPanel(ws);
        expect(
            screen.getByText("Select a layer to see its options."),
        ).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Drusen v2" }),
        );
        expect(
            screen.getByRole("region", { name: "Drusen v2" }),
        ).toBeInTheDocument();
        expect(
            screen.queryByText("Select a layer to see its options."),
        ).toBeNull();
    });

    it("a selected grid's pane shows its creator, fovea and disc edge", async () => {
        const name = BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID;
        formSchemasByName.set(name, { id: 3, name } as never);
        formAnnotations.set(11, {
            id: 11,
            form_schema_id: 3,
            image_id: "inst-a",
            annotation_type: "grader_form",
            sub_task_id: null,
            creator: { id: ME, name: `Grader ${ME}` },
            form_data: {
                fovea: { x: 512, y: 498 },
                disc_edge: { x: 801, y: 470 },
            },
        } as never);
        const ws = workspaceWith(1);
        attach(ws, 0, "inst-a");
        renderPanel(ws);
        await fireEvent.click(
            screen.getByRole("button", { name: "ETDRS grids 1" }),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: `ETDRS grid, Grader ${ME}` }),
        );
        const pane = screen.getByRole("region", {
            name: `ETDRS grid, Grader ${ME}`,
        });
        expect(within(pane).getByText("512, 498")).toBeInTheDocument();
        expect(within(pane).getByText("801, 470")).toBeInTheDocument();
    });

    it("Delete in the pane removes the selected segmentation, empties the pane and moves focus to the next row", async () => {
        for (const [id, name] of [
            [1, "Drusen v2"],
            [2, "Geographic atrophy"],
        ] as const)
            segmentations.set(
                id,
                graderSegmentation(id, ME, name, {
                    image_id: "inst-a",
                } as never),
            );
        const ws = workspaceWith(1);
        const a = attach(ws, 0, "inst-a");
        renderPanel(ws);
        await fireEvent.click(
            screen.getByRole("button", { name: "Drusen v2" }),
        );
        const pane = screen.getByRole("region", { name: "Drusen v2" });
        await fireEvent.click(
            within(pane).getByRole("button", { name: "Delete" }),
        );
        const dialog = await screen.findByRole("dialog");
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Delete" }),
        );
        await waitFor(() => expect(a.selection.value).toBeNull());
        await waitFor(
            () =>
                expect(
                    screen.getByRole("button", { name: "Geographic atrophy" }),
                ).toHaveFocus(),
            { timeout: 3000 },
        );
        expect(
            screen.getByText("Select a layer to see its options."),
        ).toBeInTheDocument();
    });
});
