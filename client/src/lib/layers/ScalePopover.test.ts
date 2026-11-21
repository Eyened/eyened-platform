import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import { formAnnotations, formSchemasByName } from "$lib/data/stores.svelte";
import type { FormAnnotationGET } from "../../types/openapi_types";
import { layersContexts, ME } from "./testContexts";

const { default: ScalePopover } = await import("./ScalePopover.svelte");
const SCHEMA_NAME = BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID;

afterEach(() => {
    cleanup();
    formAnnotations.clear();
    formSchemasByName.delete(SCHEMA_NAME);
});

/** A grid on this image with its disc edge `px` right of the fovea; null leaves the disc edge out. */
function grid(
    id: number,
    creatorId: number,
    px: number | null,
): FormAnnotationGET {
    return {
        id,
        form_schema_id: 3,
        image_id: "inst-1",
        creator: { id: creatorId, name: `Grader ${creatorId}` },
        form_data:
            px === null
                ? { fovea: { x: 0, y: 0 } }
                : { fovea: { x: 0, y: 0 }, disc_edge: { x: px, y: 0 } },
    } as unknown as FormAnnotationGET;
}

describe("ScalePopover", () => {
    it("lists stored, then your grids, the AI grid and others' grids with their scale; a grid missing a point can't be picked; a pick sets this image's scale", async () => {
        formSchemasByName.set(SCHEMA_NAME, {
            id: 3,
            name: SCHEMA_NAME,
        } as never);
        formAnnotations.set(11, grid(11, ME, 100));
        formAnnotations.set(12, grid(12, 9, 200));
        formAnnotations.set(15, grid(15, ME, null));
        const ctx = layersContexts("inst-1", {
            cfKeypoints: { fovea_xy: [0, 0], disc_edge_xy: [50, 0] },
        });
        ctx.grids.setCurrent(11);
        render(ScalePopover, {
            props: {
                layers: {
                    viewerContext: ctx.viewerContext,
                    grids: ctx.grids,
                    scale: null,
                } as never,
                empty: "No scale · lengths in px",
            },
            context: ctx.context,
        });
        await fireEvent.click(
            screen.getByRole("button", { name: /No scale · lengths in px/ }),
        );
        expect(
            screen.getByText("Stored resolution — none"),
        ).toBeInTheDocument();
        // 3 mm over 0.85 × the fovea-to-disc-edge distance: 100 px gives 35.29 µm/px, 50 px 70.59, 200 px 17.65.
        expect(
            screen
                .getAllByRole("radio")
                .map((r) => (r as HTMLInputElement).value),
        ).toEqual(["grid:11", "grid:ai", "grid:12", "typed"]);
        expect(
            screen.getByRole("radio", {
                name: "Your grid 11 · 35.29 µm/px",
            }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("radio", { name: "AI grid · 70.59 µm/px" }),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Your grid 15 · needs both points"),
        ).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("radio", {
                name: "Grader 9's grid 12 · 17.65 µm/px",
            }),
        );
        expect(ctx.workspace.scalePicks.get("inst-1")).toEqual({
            kind: "grid",
            key: 12,
        });
    });
});
