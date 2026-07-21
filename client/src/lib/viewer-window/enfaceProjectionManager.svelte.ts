import {
    getSegmentationKey,
    type Segmentation,
} from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import { EnfaceProjection } from "$lib/webgl/enfaceProjection";
import type { Image2D } from "$lib/webgl/image2D";
import type { Image3D } from "$lib/webgl/image3D";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import { SvelteMap } from "svelte/reactivity";

function isProjectable(segmentation: Segmentation): boolean {
    if (segmentation.image_projection_matrix) {
        return false;
    }
    const rep = segmentation.data_representation;
    return (
        rep === "Binary" ||
        rep === "DualBitMask" ||
        rep === "Probability"
    );
}

export class EnfaceProjectionManager {
    private readonly projections = new SvelteMap<string, EnfaceProjection>();
    private readonly attachedItems = new SvelteMap<string, SegmentationItem>();
    mainViewerContext: MainViewerContext | undefined;

    constructor(
        readonly octImage: Image3D,
        readonly projImage: Image2D,
    ) {}

    registerMainViewerContext(mainViewerContext: MainViewerContext): void {
        this.mainViewerContext = mainViewerContext;
        this.attachExistingSegmentations();
    }

    private attachExistingSegmentations(): void {
        const ctx = this.mainViewerContext?.segmentationContext;
        if (!ctx) {
            return;
        }
        for (const segmentation of [
            ...ctx.graderSegmentations,
            ...ctx.modelSegmentations,
        ]) {
            if (!isProjectable(segmentation)) {
                continue;
            }
            const item = ctx.getSegmentationItem(segmentation);
            this.attachSegmentationItem(item);
        }
    }

    attachSegmentationItem(item: SegmentationItem): void {
        if (!isProjectable(item.segmentation)) {
            return;
        }

        const key = getSegmentationKey(item.segmentation);
        const alreadyAttached = this.attachedItems.has(key);

        if (!alreadyAttached) {
            this.attachedItems.set(key, item);
            item.onSliceChanged = (scanNr) => {
                this.onSliceChanged(item, scanNr);
            };

            if (!this.projections.has(key)) {
                const { webgl, width, depth } = this.octImage;
                this.projections.set(
                    key,
                    new EnfaceProjection(webgl.gl, webgl.shaders, width, depth),
                );
            }
        }

        void this.projectAllWhenReady(item);
    }

    private async projectAllWhenReady(item: SegmentationItem): Promise<void> {
        if (item.ready) {
            try {
                await item.ready;
            } catch (error) {
                console.error(
                    "EnfaceProjectionManager: failed to load segmentation volume",
                    error,
                );
            }
        }

        const key = getSegmentationKey(item.segmentation);
        if (!this.attachedItems.has(key)) {
            return;
        }

        this.getProjection(item).projectAll(item, this.octImage.height);
    }

    onSliceChanged(item: SegmentationItem, scanNr: number): void {
        const projection = this.projections.get(
            getSegmentationKey(item.segmentation),
        );
        if (!projection) {
            return;
        }

        const state = item.segmentationStates.get(scanNr);
        if (!state) {
            projection.clearSlice(scanNr);
            return;
        }

        projection.projectSlice(scanNr, state.mask, this.octImage.height);
    }

    getVisibleProjections(): {
        segmentation: Segmentation;
        segmentationItem: SegmentationItem;
        projection: EnfaceProjection;
    }[] {
        const ctx = this.mainViewerContext?.segmentationContext;
        if (!ctx) {
            return [];
        }

        const result: {
            segmentation: Segmentation;
            segmentationItem: SegmentationItem;
            projection: EnfaceProjection;
        }[] = [];

        for (const segmentation of [
            ...ctx.visibleGraderSegmentations,
            ...ctx.visibleModelSegmentations,
        ]) {
            if (!isProjectable(segmentation)) {
                continue;
            }
            const key = getSegmentationKey(segmentation);
            const segmentationItem = ctx.getSegmentationItem(segmentation);
            this.attachSegmentationItem(segmentationItem);
            const projection = this.projections.get(key);
            if (!projection) {
                continue;
            }
            result.push({ segmentation, segmentationItem, projection });
        }

        return result;
    }

    get maxThickness(): number {
        return Math.max(1, this.octImage.height);
    }

    dispose(): void {
        for (const projection of this.projections.values()) {
            projection.dispose();
        }
        this.projections.clear();
        this.attachedItems.clear();
        this.mainViewerContext = undefined;
    }

    private getProjection(item: SegmentationItem): EnfaceProjection {
        const key = getSegmentationKey(item.segmentation);
        let projection = this.projections.get(key);
        if (!projection) {
            const { webgl, width, depth } = this.octImage;
            projection = new EnfaceProjection(
                webgl.gl,
                webgl.shaders,
                width,
                depth,
            );
            this.projections.set(key, projection);
        }
        return projection;
    }
}
