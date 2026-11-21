import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import { formAnnotations, formSchemasByName } from "$lib/data/stores.svelte";
import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import type { FormAnnotationGET } from "../../types/openapi_types";
import { AI_GRID } from "./gridLayers.svelte";
import type { Scale } from "./imageScale";
import { layersContexts, ME } from "./testContexts";

vi.mock("$lib/data/api", async (original) => ({
    ...(await original<typeof import("$lib/data/api")>()),
    createFormAnnotation: vi.fn(),
    deleteFormAnnotation: vi.fn(async (id: number) => {
        formAnnotations.delete(id);
    }),
}));

const { createFormAnnotation, deleteFormAnnotation } = await import(
    "$lib/data/api"
);
const { default: EtdrsSection } = await import("./EtdrsSection.svelte");

const SCHEMA_NAME = BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID;
const KEYPOINTS = { fovea_xy: [10, 11], disc_edge_xy: [20, 21] };

afterEach(() => {
    cleanup();
    formAnnotations.clear();
    formSchemasByName.delete(SCHEMA_NAME);
});

/** A synthetic ETDRS grid on `imageId`, outside any subtask unless `over` says so. */
function grid(
    id: number,
    creatorId: number,
    imageId = "inst-1",
    over: Partial<FormAnnotationGET> = {},
): FormAnnotationGET {
    return {
        id,
        form_schema_id: 3,
        image_id: imageId,
        patient_id: 1,
        annotation_type: "grader_form",
        sub_task_id: null,
        creator: { id: creatorId, name: `Grader ${creatorId}` },
        form_data: { fovea: { x: 512, y: 498 }, disc_edge: { x: 801, y: 470 } },
        ...over,
    } as unknown as FormAnnotationGET;
}

/** The PointTool among the overlays added so far, with its disposer. */
function pointTool(addOverlay: ReturnType<typeof vi.fn>) {
    const i = addOverlay.mock.calls.findIndex(
        ([overlay]) => overlay instanceof PointTool,
    );
    return {
        tool: addOverlay.mock.calls[i]?.[0] as PointTool | undefined,
        dispose: addOverlay.mock.results[i]?.value as
            | ReturnType<typeof vi.fn>
            | undefined,
    };
}

function renderSection(
    over: Parameters<typeof layersContexts>[1] = {},
    subTaskId?: number,
    props: {
        open?: boolean;
        ontoggle?: () => void;
        scale?: Scale | null;
    } = {},
) {
    formSchemasByName.set(SCHEMA_NAME, { id: 3, name: SCHEMA_NAME } as never);
    const ctx = layersContexts("inst-1", over);
    const context = new Map(ctx.context);
    if (subTaskId !== undefined)
        context.set("taskContext", { subTask: { id: subTaskId } });
    const view = render(EtdrsSection, {
        props: {
            grids: ctx.grids,
            open: true,
            ontoggle: vi.fn(),
            scale: null,
            ...props,
        },
        context,
    });
    return { ...ctx, ...view };
}

describe("EtdrsSection", () => {
    it("lists the AI grid, this image's grids, then linked grids, and tags this task's grids", async () => {
        formAnnotations.set(12, grid(12, 9));
        formAnnotations.set(11, grid(11, ME, "inst-1", { sub_task_id: 7 }));
        formAnnotations.set(13, grid(13, 8, "inst-2", { sub_task_id: 7 }));
        const { container } = renderSection(
            { cfKeypoints: KEYPOINTS, linked: ["inst-2"] },
            7,
        );
        expect(
            screen
                .getAllByRole("group", { name: /grid/ })
                .map((group) => group.getAttribute("aria-label")),
        ).toEqual([
            "AI grid",
            "ETDRS grid, Grader 5 [11]",
            "ETDRS grid, Grader 9 [12]",
            "ETDRS grid, Grader 8 [13]",
        ]);
        expect(
            screen.getByRole("list", { name: "Linked from registered images" }),
        ).toBeInTheDocument();
        expect(
            screen
                .getAllByText("This task")
                .map((tag) =>
                    tag.closest("[role=group]")?.getAttribute("aria-label"),
                ),
        ).toEqual(["ETDRS grid, Grader 5 [11]", "ETDRS grid, Grader 8 [13]"]);
        await expectNoAxeViolations(container);
    });

    it("tags the grid that gives the scale", () => {
        formAnnotations.set(11, grid(11, ME));
        formAnnotations.set(12, grid(12, 9));
        renderSection({}, undefined, {
            scale: {
                x: 10,
                y: 10,
                source: "from grid 12",
                pick: { kind: "grid", key: 12 },
            },
        });
        expect(
            within(
                screen.getByRole("group", {
                    name: "ETDRS grid, Grader 9 [12]",
                }),
            ).getByText("Scale"),
        ).toBeInTheDocument();
        expect(
            within(
                screen.getByRole("group", {
                    name: `ETDRS grid, Grader ${ME} [11]`,
                }),
            ).queryByText("Scale"),
        ).toBeNull();
    });

    it("the name sets and unsets the current grid; the section mounts no tool", async () => {
        formAnnotations.set(11, grid(11, ME));
        const { viewerContext, grids } = renderSection();
        const name = () =>
            screen.getByRole("button", { name: "ETDRS grid, Grader 5" });
        await fireEvent.click(name());
        expect(grids.isShown(11)).toBe(false);
        expect(name()).toHaveAttribute("aria-pressed", "true");
        // Only the grid overlay mounts, so a click with Pan or Distance armed places nothing.
        expect(
            pointTool(vi.mocked(viewerContext.addOverlay)).tool,
        ).toBeUndefined();
        await fireEvent.click(name());
        expect(name()).toHaveAttribute("aria-pressed", "false");
    });

    it("New opens a closed section, hides every grid, creates one in this task, makes it current and arms Place ETDRS at Fovea", async () => {
        formAnnotations.set(11, grid(11, ME));
        const ontoggle = vi.fn();
        const view = renderSection({ cfKeypoints: KEYPOINTS }, 7, {
            open: false,
            ontoggle,
        });
        ontoggle.mockImplementation(() => view.rerender({ open: true }));
        const { grids, workspace } = view;
        workspace.etdrsSlot = 1;
        grids.setCurrent(11);
        grids.setShown(AI_GRID, true);
        vi.mocked(createFormAnnotation).mockImplementation(async () => {
            const created = grid(99, ME, "inst-1", {
                sub_task_id: 7,
                form_data: {},
            });
            formAnnotations.set(99, created);
            return created;
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "New ETDRS grid" }),
        );
        await vi.waitFor(() => expect(grids.currentId).toBe(99));
        expect(ontoggle).toHaveBeenCalledOnce();
        expect(createFormAnnotation).toHaveBeenCalledWith(
            expect.objectContaining({
                form_schema_id: 3,
                image_id: "inst-1",
                sub_task_id: 7,
            }),
        );
        expect([
            grids.isShown(11),
            grids.isShown(AI_GRID),
            grids.isShown(99),
        ]).toEqual([false, false, true]);
        expect(workspace.arm).toHaveBeenCalledWith("etdrs");
        expect(workspace.etdrsSlot).toBe(0);
        const name = within(
            screen.getByRole("group", { name: "ETDRS grid, Grader 5 [99]" }),
        ).getByRole("button", { name: "ETDRS grid, Grader 5" });
        await vi.waitFor(() => expect(name).toHaveFocus());
    });

    it("Delete asks first, then deletes your grid and unsets it", async () => {
        formAnnotations.set(11, grid(11, ME));
        formAnnotations.set(12, grid(12, 9));
        const { grids } = renderSection();
        grids.setCurrent(11);
        grids.setShown(11, true);
        expect(
            within(
                screen.getByRole("group", {
                    name: "ETDRS grid, Grader 9 [12]",
                }),
            ).queryByRole("button", { name: "Delete" }),
        ).toBeNull();
        await fireEvent.click(
            within(
                screen.getByRole("group", {
                    name: "ETDRS grid, Grader 5 [11]",
                }),
            ).getByRole("button", { name: "Delete" }),
        );
        const dialog = await screen.findByRole("dialog");
        expect(within(dialog).getByText("Delete grid")).toBeInTheDocument();
        expect(
            within(dialog).getByText("ETDRS grid · Grader 5 [11]"),
        ).toBeInTheDocument();
        expect(deleteFormAnnotation).not.toHaveBeenCalled();
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Delete" }),
        );
        await vi.waitFor(() => expect(grids.currentId).toBeUndefined());
        expect(deleteFormAnnotation).toHaveBeenCalledWith(11);
        expect(grids.isShown(11)).toBe(false);
    });
});
