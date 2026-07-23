import {
    getSegmentationKey,
    type Segmentation,
} from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import {
    getEnfaceFeatureIndices,
    getEnfaceLayerKey,
    isMultiFeatureEnfaceSegmentation,
    isProjectable,
    SIMPLE_ENFACE_FEATURE_INDEX,
} from "$lib/viewer-window/enfaceProjectionKeys";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import { EnfaceProjection } from "$lib/webgl/enfaceProjection";
import type { Image2D } from "$lib/webgl/image2D";
import type { Image3D } from "$lib/webgl/image3D";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import { SvelteMap } from "svelte/reactivity";

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

        const segmentationKey = getSegmentationKey(item.segmentation);
        const alreadyAttached = this.attachedItems.has(segmentationKey);

        if (!alreadyAttached) {
            this.attachedItems.set(segmentationKey, item);
            item.onSliceChanged = (scanNr) => {
                this.onSliceChanged(item, scanNr);
            };

            for (const featureIndex of getEnfaceFeatureIndices(
                item.segmentation,
            )) {
                this.getProjection(item, featureIndex);
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

        const segmentationKey = getSegmentationKey(item.segmentation);
        if (!this.attachedItems.has(segmentationKey)) {
            return;
        }

        if (isMultiFeatureEnfaceSegmentation(item.segmentation)) {
            // Task 3: project all layers for MC/ML.
            return;
        }

        this.getProjection(item, SIMPLE_ENFACE_FEATURE_INDEX).projectAll(
            item,
            this.octImage.height,
        );
    }

    onSliceChanged(item: SegmentationItem, scanNr: number): void {
        const segmentationKey = getSegmentationKey(item.segmentation);

        if (isMultiFeatureEnfaceSegmentation(item.segmentation)) {
            // Task 3: reproject all layers for MC/ML.
            return;
        }

        const projection = this.projections.get(
            getEnfaceLayerKey(segmentationKey, SIMPLE_ENFACE_FEATURE_INDEX),
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
        featureIndex: number;
    }[] {
        const ctx = this.mainViewerContext?.segmentationContext;
        if (!ctx) {
            return [];
        }

        const result: {
            segmentation: Segmentation;
            segmentationItem: SegmentationItem;
            projection: EnfaceProjection;
            featureIndex: number;
        }[] = [];

        for (const segmentation of [
            ...ctx.visibleGraderSegmentations,
            ...ctx.visibleModelSegmentations,
        ]) {
            if (!isProjectable(segmentation)) {
                continue;
            }

            if (isMultiFeatureEnfaceSegmentation(segmentation)) {
                // Task 4: filter by activeIndices.
                continue;
            }

            const segmentationKey = getSegmentationKey(segmentation);
            const segmentationItem = ctx.getSegmentationItem(segmentation);
            this.attachSegmentationItem(segmentationItem);
            const projection = this.projections.get(
                getEnfaceLayerKey(
                    segmentationKey,
                    SIMPLE_ENFACE_FEATURE_INDEX,
                ),
            );
            if (!projection) {
                continue;
            }
            result.push({
                segmentation,
                segmentationItem,
                projection,
                featureIndex: SIMPLE_ENFACE_FEATURE_INDEX,
            });
        }

        return result;
    }

    dispose(): void {
        for (const projection of this.projections.values()) {
            projection.dispose();
        }
        this.projections.clear();
        this.attachedItems.clear();
        this.mainViewerContext = undefined;
    }

    private getProjection(
        item: SegmentationItem,
        featureIndex: number,
    ): EnfaceProjection {
        const segmentationKey = getSegmentationKey(item.segmentation);
        const layerKey = getEnfaceLayerKey(segmentationKey, featureIndex);
        let projection = this.projections.get(layerKey);
        if (!projection) {
            const { webgl, width, depth } = this.octImage;
            projection = new EnfaceProjection(
                webgl.gl,
                webgl.shaders,
                width,
                depth,
            );
            this.projections.set(layerKey, projection);
        }
        return projection;
    }
}
