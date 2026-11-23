import {
    getSegmentationKey,
    type Segmentation,
    type SegmentationContext,
} from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import {
    getEnfaceFeatureIndices,
    getEnfaceLayerKey,
    isProjectable,
} from "$lib/viewer-window/enfaceProjectionKeys";
import {
    classWinners,
    enumerateVisibleEnfaceLayers,
} from "$lib/viewer-window/enfaceProjectionVisibility";
import type { EnfaceProjectionMode } from "$lib/viewer/viewer-utils";
import { TextureData } from "$lib/webgl/texture";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import type { Color } from "$lib/utils";
import { EnfaceProjection } from "$lib/webgl/enfaceProjection";
import type { Image3D } from "$lib/webgl/image3D";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";

export type VisibleEnfaceProjection = {
    segmentation: Segmentation;
    segmentationItem: SegmentationItem;
    projection: EnfaceProjection;
    featureIndex: number;
    color: Color;
    /** Layer weight before main viewer alpha (matches B-scan MC/ML shaders). */
    layerAlpha: number;
};

/** What the overlay paints: one projection, or one MultiClass segmentation's class map (class numbers; the shader colours them). */
export type EnfacePaintLayer =
    | ({ kind: "projection" } & Pick<
          VisibleEnfaceProjection,
          "projection" | "color" | "layerAlpha"
      >)
    | {
          kind: "classMap";
          texture: WebGLTexture;
          /** The active class; 0 for none. */
          active: number;
          activeAlpha: number;
          inactiveAlpha: number;
      };

/** A viewport showing this OCT; the newest one is the projection's source. */
export interface ProjectionSourceViewport {
    readonly mainViewerContext: MainViewerContext;
    /** The viewport's 0-based position; it follows a swap. */
    position(): number;
}

export class EnfaceProjectionManager {
    // Imperative caches only (RAF repaint / slice callbacks) — not read from
    // $effect/$derived, so SvelteMap would add proxy cost with no benefit.
    // eslint-disable-next-line svelte/prefer-svelte-reactivity -- see above
    private readonly projections = new Map<string, EnfaceProjection>();
    // eslint-disable-next-line svelte/prefer-svelte-reactivity -- see above
    private readonly attachedItems = new Map<string, SegmentationItem>();
    // eslint-disable-next-line svelte/prefer-svelte-reactivity -- see above
    private readonly classMaps = new Map<
        string,
        { textureData: TextureData; key: string }
    >();
    /** Bumped whenever a projection changes, so class maps rebuild. */
    private revision = 0;
    private viewports: ProjectionSourceViewport[] = $state.raw([]);

    constructor(readonly octImage: Image3D) {}

    /** The OCT viewport opened last; undefined while the OCT is open nowhere. */
    get source(): ProjectionSourceViewport | undefined {
        return this.viewports.at(-1);
    }

    get mainViewerContext(): MainViewerContext | undefined {
        return this.source?.mainViewerContext;
    }

    /** Adds a viewport showing this OCT; call the returned function when it closes. */
    register(viewport: ProjectionSourceViewport): () => void {
        this.viewports = [...this.viewports, viewport];
        this.attachExistingSegmentations();
        return () => {
            this.viewports = this.viewports.filter((v) => v !== viewport);
        };
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
        this.revision++;
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
        this.revision++;
    }

    private getVisibleProjections(): VisibleEnfaceProjection[] {
        const ctx = this.mainViewerContext?.segmentationContext;
        if (!ctx) {
            return [];
        }

        for (const segmentation of [
            ...ctx.visibleGraderSegmentations,
            ...ctx.visibleModelSegmentations,
        ]) {
            if (isProjectable(segmentation)) {
                this.ensureAttached(ctx.getSegmentationItem(segmentation));
            }
        }

        return enumerateVisibleEnfaceLayers(
            ctx,
            this.mainViewerContext,
            this.attachedItems,
        )
            .map(
                ({
                    segmentation,
                    segmentationItem,
                    featureIndex,
                    layerAlpha,
                    color,
                }) => {
                    const layerKey = getEnfaceLayerKey(
                        getSegmentationKey(segmentation),
                        featureIndex,
                    );
                    const projection = this.projections.get(layerKey);
                    if (!projection) {
                        return null;
                    }
                    return {
                        segmentation,
                        segmentationItem,
                        projection,
                        featureIndex,
                        color,
                        layerAlpha,
                    };
                },
            )
            .filter(
                (entry): entry is VisibleEnfaceProjection => entry !== null,
            );
    }

    /** Layers in list order. MultiClass paints one class map in Mask and only the active class in Thickness. */
    getPaintLayers(mode: EnfaceProjectionMode): EnfacePaintLayer[] {
        const ctx = this.mainViewerContext?.segmentationContext;
        if (!ctx) {
            return [];
        }
        const active =
            typeof ctx.activeIndices === "number"
                ? ctx.activeIndices
                : undefined;
        const layers: EnfacePaintLayer[] = [];
        const mapped: string[] = [];
        for (const entry of this.getVisibleProjections()) {
            const { projection, color, layerAlpha } = entry;
            if (entry.segmentation.data_representation !== "MultiClass") {
                layers.push({
                    kind: "projection",
                    projection,
                    color,
                    layerAlpha,
                });
                continue;
            }
            if (mode === "heatmap") {
                if (entry.featureIndex === active) {
                    layers.push({
                        kind: "projection",
                        projection,
                        color,
                        layerAlpha,
                    });
                }
                continue;
            }
            const key = getSegmentationKey(entry.segmentation);
            if (mapped.includes(key)) {
                continue;
            }
            mapped.push(key);
            layers.push({
                kind: "classMap",
                texture: this.classMap(entry.segmentation, ctx, active),
                active: active ?? 0,
                activeAlpha: ctx.multiClassActiveAlpha,
                inactiveAlpha: ctx.multiClassInactiveAlpha,
            });
        }
        return layers;
    }

    /** The segmentation's class numbers per en-face pixel, rebuilt only when its projections, active class or visible classes changed. */
    private classMap(
        segmentation: Segmentation,
        ctx: SegmentationContext,
        active: number | undefined,
    ): WebGLTexture {
        const segmentationKey = getSegmentationKey(segmentation);
        const shown = getEnfaceFeatureIndices(segmentation).filter((i) =>
            ctx.isFeatureLayerVisible(segmentation, i),
        );
        const key = [this.revision, active, shown.join(",")].join("|");
        let entry = this.classMaps.get(segmentationKey);
        if (!entry) {
            const { webgl, width, depth } = this.octImage;
            entry = {
                textureData: new TextureData(webgl.gl, width, depth, "R8"),
                key: "",
            };
            this.classMaps.set(segmentationKey, entry);
        }
        if (entry.key !== key) {
            // Reading `data` copies a projection back from the GPU, so only shown classes are read.
            const classes = shown.flatMap((index) => {
                const projection = this.projections.get(
                    getEnfaceLayerKey(segmentationKey, index),
                );
                return projection
                    ? [
                          {
                              index,
                              values: projection.textureData.data as Uint8Array,
                          },
                      ]
                    : [];
            });
            entry.textureData.uploadData(
                // eslint-disable-next-line svelte/prefer-svelte-reactivity -- throwaway argument
                classWinners(classes, active, new Set(shown)),
            );
            entry.key = key;
        }
        return entry.textureData.texture;
    }

    dispose(): void {
        for (const projection of this.projections.values()) {
            projection.dispose();
        }
        for (const { textureData } of this.classMaps.values()) {
            textureData.dispose();
        }
        this.classMaps.clear();
        this.projections.clear();
        this.attachedItems.clear();
        this.viewports = [];
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
