import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import { formAnnotations, formSchemasByName } from "$lib/data";
import type { PointList } from "$lib/forms/pointSchema";
import type { Registration } from "$lib/registration/registration.svelte";
import {
    ETDRSGridItemOverlay,
    gridPointsIn,
    type ETDRSGridSource,
    type etdrsGridType,
    type GridData,
} from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { ScaleGrid } from "./imageScale";
import { SvelteMap } from "svelte/reactivity";
import type { FormAnnotationGET } from "../../types/openapi_types";

/** The AI grid's key among the shown grids. */
export const AI_GRID = "ai";
export type GridKey = number | typeof AI_GRID;

/** The model's grid for an image, from its fovea and disc-edge keypoints; undefined unless it has both. */
export function aiGrid(image: AbstractImage): etdrsGridType | undefined {
    const fovea = image.instance.cf_keypoints?.fovea_xy;
    const disc = image.instance.cf_keypoints?.disc_edge_xy;
    // The model can return one keypoint without the other.
    if (!fovea || !disc) return undefined;
    const [fx, fy] = fovea as [number, number];
    const [dx, dy] = disc as [number, number];
    return {
        image_id: String(image.image_id),
        form_data: { fovea: { x: fx, y: fy }, disc_edge: { x: dx, y: dy } },
    };
}

/** Whether a grid was made in this task's subtask. */
export function isThisTask(
    grid: FormAnnotationGET,
    subTaskId: number | undefined,
): boolean {
    return grid.sub_task_id === subTaskId;
}

/** The grid Place ETDRS writes in a viewport, or why it can't. */
export interface GridTarget {
    name: string | null;
    reason: string | null;
}

/** Place ETDRS writes the viewport's current grid only if it is yours and on this image. */
export function gridBinding(input: {
    grid: FormAnnotationGET | undefined;
    instanceId: string | number;
    userId: number;
    canEdit: (grid: FormAnnotationGET) => boolean;
}): GridTarget {
    const { grid } = input;
    if (!grid)
        return {
            name: null,
            reason: "No current grid. Choose one in ETDRS grids.",
        };
    const name =
        grid.creator.id === input.userId
            ? `Your grid ${grid.id}`
            : `${grid.creator.name}'s grid ${grid.id}`;
    if (!input.canEdit(grid))
        return { name, reason: "Another grader's grid can't be edited." };
    if (String(grid.image_id) !== String(input.instanceId))
        return { name, reason: "This grid is on another image." };
    return { name, reason: null };
}

/** Keep grid size: a moved fovea takes the disc edge along, so the grid's size and direction stay. */
export function keepGridSize(before: PointList, after: PointList): PointList {
    const [f0, d0] = before;
    const [f1, d1] = after;
    if (!f0 || !f1 || !d0 || !d1) return after;
    // The disc edge itself moved, or nothing did.
    if (d1.x !== d0.x || d1.y !== d0.y) return after;
    const dx = f1.x - f0.x;
    const dy = f1.y - f0.y;
    if (dx === 0 && dy === 0) return after;
    return [f1, { ...d1, x: d1.x + dx, y: d1.y + dy }];
}

/** One viewport's ETDRS grids: which show, the current grid and its armed slot. */
export class GridLayers {
    currentId: number | undefined = $state();
    private armedSlot: { id: number; index: number } | undefined = $state();
    private readonly shown = new SvelteMap<GridKey, () => void>();

    constructor(
        readonly viewerContext: ViewerContext,
        private readonly registration: Registration,
        /** Sizes every grid in this viewport, the AI grid included. */
        private readonly settings: { readonly radiusFraction: number },
    ) {}

    /** ETDRS grids on this image or on an image registered to it, oldest first. */
    list(): FormAnnotationGET[] {
        const schemaId = formSchemasByName.get(
            BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID,
        )?.id;
        if (schemaId === undefined) return [];
        const { image } = this.viewerContext;
        const linked = this.registration.getLinkedImgIds(image.image_id);
        return formAnnotations
            .filter(
                (f) =>
                    f.form_schema_id === schemaId &&
                    (f.image_id == image.instance.id ||
                        linked.has(`${f.image_id}`) ||
                        linked.has(`${f.image_id}_proj`)),
            )
            .sort((a, b) => a.id - b.id);
    }

    isShown(key: GridKey): boolean {
        return this.shown.has(key);
    }

    /** The keys of the grids shown in this viewport. */
    shownKeys(): GridKey[] {
        return [...this.shown.keys()];
    }

    /** Each listed grid, then the AI grid, with its points in this image's pixels. */
    scaleGrids(): ScaleGrid[] {
        const { image } = this.viewerContext;
        const into = (gridImageId: string, data: unknown) =>
            gridPointsIn(
                this.registration,
                gridImageId,
                data as GridData | null,
                image.image_id,
            );
        const grids: ScaleGrid[] = this.list().map((grid) => ({
            key: grid.id,
            ...into(String(grid.image_id), grid.form_data),
        }));
        const ai = aiGrid(image);
        if (ai) grids.push({ key: AI_GRID, ...into(ai.image_id, ai.form_data) });
        return grids;
    }

    setShown(key: GridKey, on: boolean): void {
        if (on === this.shown.has(key)) return;
        if (!on) {
            this.shown.get(key)?.();
            this.shown.delete(key);
            return;
        }
        let source: ETDRSGridSource;
        if (key === AI_GRID) {
            const data = aiGrid(this.viewerContext.image);
            if (!data) return;
            source = { kind: "snapshot", data };
        } else {
            source = { kind: "annotation", id: key };
        }
        this.shown.set(
            key,
            this.viewerContext.addOverlay(
                new ETDRSGridItemOverlay(
                    source,
                    this.registration,
                    this.settings,
                ),
            ),
        );
    }

    hideAll(): void {
        for (const key of [...this.shown.keys()]) this.setShown(key, false);
    }

    /** Remembers a grid's armed slot: 0 fovea, 1 disc edge. */
    saveSlot(id: number, index: number): void {
        this.armedSlot = { id, index };
    }

    /** The slot saved for a grid; Fovea when none was. */
    slotOf(id: number): number {
        return this.armedSlot?.id === id ? this.armedSlot.index : 0;
    }

    /** Sets the current grid, which shows it and arms Fovea; undefined unsets it. */
    setCurrent(id: number | undefined): void {
        this.currentId = id;
        if (id === undefined) return;
        this.armedSlot = undefined;
        this.setShown(id, true);
    }

    /** Drops a deleted grid. */
    forget(id: number): void {
        this.setShown(id, false);
        if (this.currentId === id) this.currentId = undefined;
    }
}
