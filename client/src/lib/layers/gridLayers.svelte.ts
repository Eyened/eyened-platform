import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import { formAnnotations, formSchemasByName } from "$lib/data";
import type { Registration } from "$lib/registration/registration.svelte";
import {
    ETDRSGridItemOverlay,
    type ETDRSGridSource,
    type etdrsGridType,
} from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { SvelteMap } from "svelte/reactivity";
import type { FormAnnotationGET } from "../../types/openapi_types";

/** The AI grid's key among the shown grids. */
export const AI_GRID = "ai";
export type GridKey = number | typeof AI_GRID;

/** The model's grid for an image, from its fovea and disc-edge keypoints; undefined when it has none. */
export function aiGrid(image: AbstractImage): etdrsGridType | undefined {
    const keypoints = image.instance.cf_keypoints;
    if (!keypoints) return undefined;
    const [fx, fy] = keypoints.fovea_xy as [number, number];
    const [dx, dy] = keypoints.disc_edge_xy as [number, number];
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

/** One viewport's ETDRS grids: which show, the current grid and its armed slot, and the radius fraction. */
export class GridLayers {
    /** Sizes every grid in this viewport, the AI grid included. */
    readonly settings = $state({ radiusFraction: 0.85 });
    currentId: number | undefined = $state();
    /** The current grid's armed slot: 0 fovea, 1 disc edge. */
    slot = $state(0);
    private readonly shown = new SvelteMap<GridKey, () => void>();

    constructor(
        readonly viewerContext: ViewerContext,
        private readonly registration: Registration,
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

    /** Sets the current grid, which shows it and arms Fovea; undefined unsets it. */
    setCurrent(id: number | undefined): void {
        this.currentId = id;
        if (id === undefined) return;
        this.slot = 0;
        this.setShown(id, true);
    }

    /** Drops a deleted grid. */
    forget(id: number): void {
        this.setShown(id, false);
        if (this.currentId === id) this.currentId = undefined;
    }
}
