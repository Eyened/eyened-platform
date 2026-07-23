import {
    getSegmentationKey,
    type Segmentation,
} from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import {
    getEnfaceFeatureIndices,
    getEnfaceLayerKey,
    getEnfaceLayerAlpha,
    getSubfeatureColor,
    isEnfaceLayerVisible,
    isMultiFeatureEnfaceSegmentation,
    isProjectable,
} from "$lib/viewer-window/enfaceProjectionKeys";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import { colors } from "$lib/viewer/overlays/colors";
import type { Color } from "$lib/utils";
import { EnfaceProjection } from "$lib/webgl/enfaceProjection";
import type { Image3D } from "$lib/webgl/image3D";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import { SvelteMap } from "svelte/reactivity";

export type VisibleEnfaceProjection = {
    segmentation: Segmentation;
    segmentationItem: SegmentationItem;
    projection: EnfaceProjection;
    featureIndex: number;
    color: Color;
    /** Layer weight before main viewer alpha (matches B-scan MC/ML shaders). */
    layerAlpha: number;
};

export class EnfaceProjectionManager {
    private readonly projections = new SvelteMap<string, EnfaceProjection>();
    private readonly attachedItems = new SvelteMap<string, SegmentationItem>();
    mainViewerContext: MainViewerContext | undefined;

    constructor(readonly octImage: Image3D) {}

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

            void this.projectAllWhenReady(item);
        }
    }

    private ensureAttached(item: SegmentationItem): boolean {
        if (!isProjectable(item.segmentation)) {
            return false;
        }
        if (!this.attachedItems.has(getSegmentationKey(item.segmentation))) {
            this.attachSegmentationItem(item);
        }
        return this.attachedItems.has(getSegmentationKey(item.segmentation));
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

        const bscanHeight = this.octImage.height;
        for (const featureIndex of getEnfaceFeatureIndices(item.segmentation)) {
            this.getProjection(item, featureIndex).projectAllLayers(
                item,
                featureIndex,
                bscanHeight,
            );
        }
    }

    onSliceChanged(item: SegmentationItem, scanNr: number): void {
        const state = item.segmentationStates.get(scanNr);
        const bscanHeight = this.octImage.height;

        for (const featureIndex of getEnfaceFeatureIndices(item.segmentation)) {
            const projection = this.getProjection(item, featureIndex);
            if (!state) {
                projection.clearSlice(scanNr);
            } else {
                projection.projectSliceForFeature(
                    scanNr,
                    state.mask,
                    featureIndex,
                    bscanHeight,
                );
            }
        }
    }

    getVisibleProjections(): VisibleEnfaceProjection[] {
        const ctx = this.mainViewerContext?.segmentationContext;
        if (!ctx) {
            return [];
        }

        const result: VisibleEnfaceProjection[] = [];

        for (const segmentation of [
            ...ctx.visibleGraderSegmentations,
            ...ctx.visibleModelSegmentations,
        ]) {
            if (!isProjectable(segmentation)) {
                continue;
            }

            const segmentationKey = getSegmentationKey(segmentation);
            const segmentationItem = ctx.getSegmentationItem(segmentation);
            if (!this.ensureAttached(segmentationItem)) {
                continue;
            }

            for (const featureIndex of getEnfaceFeatureIndices(segmentation)) {
                if (
                    !isEnfaceLayerVisible(segmentation, featureIndex, ctx)
                ) {
                    continue;
                }

                const layerAlpha = getEnfaceLayerAlpha(
                    segmentation,
                    featureIndex,
                    ctx,
                    this.mainViewerContext?.highlightedFeatureIndex,
                );
                if (layerAlpha <= 0) {
                    continue;
                }

                const projection = this.projections.get(
                    getEnfaceLayerKey(segmentationKey, featureIndex),
                );
                if (!projection) {
                    continue;
                }

                result.push({
                    segmentation,
                    segmentationItem,
                    projection,
                    featureIndex,
                    color: this.getEnfaceLayerColor(segmentation, featureIndex),
                    layerAlpha,
                });
            }
        }

        return result;
    }

    private getEnfaceLayerColor(
        segmentation: Segmentation,
        featureIndex: number,
    ): Color {
        if (isMultiFeatureEnfaceSegmentation(segmentation)) {
            return getSubfeatureColor(featureIndex);
        }

        return (
            this.mainViewerContext?.getFeatureColor(segmentation) ?? colors[0]
        );
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
