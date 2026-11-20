import { createSegmentationFrom } from "$lib/data";
import type { GlobalContext } from "$lib/data/globalContext.svelte";
import type {
    FeatureGET,
    SegmentationDataRepresentation,
    SegmentationDataType,
} from "../../../types/openapi_types";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type {
    Segmentation,
    SegmentationContext,
} from "./segmentationContext.svelte";
import {
    imageBoxHeight,
    imageBoxWidth,
    projectionMatrixFromBox,
    type ImageBox,
} from "./segmentationRegion";

export const SEGMENTATION_TYPES = ["Q", "B", "P"] as const;
export type SegmentationTypeCode = (typeof SEGMENTATION_TYPES)[number];

export const SEGMENTATION_TYPE_OPTIONS = [
    { value: "Q", label: "Questionable" },
    { value: "B", label: "Binary" },
    { value: "P", label: "Probability" },
    { value: "MultiClass", label: "Multi-class" },
    { value: "MultiLabel", label: "Multi-label" },
] as const;

export type SegmentationTypeChoice =
    (typeof SEGMENTATION_TYPE_OPTIONS)[number]["value"];

export function isMultiSegmentationType(
    type: SegmentationTypeChoice,
): type is "MultiClass" | "MultiLabel" {
    return type === "MultiClass" || type === "MultiLabel";
}

export const DATA_REPRESENTATION_BY_TYPE: Record<
    SegmentationTypeCode,
    SegmentationDataRepresentation
> = {
    Q: "DualBitMask",
    B: "Binary",
    P: "Probability",
};

export function dataRepresentationForType(
    type: SegmentationTypeChoice,
): SegmentationDataRepresentation {
    if (isMultiSegmentationType(type)) {
        return type;
    }
    return DATA_REPRESENTATION_BY_TYPE[type];
}

export function dataTypeForType(
    type: SegmentationTypeChoice,
): SegmentationDataType {
    return type === "P" ? "R8" : "R8UI";
}

export type CreateSegmentationDialogMode = "full" | "region";

function activateCreated(
    segmentationContext: SegmentationContext,
    segmentation: Segmentation,
    creatorId: number,
) {
    segmentationContext.activateForDrawing(segmentation, creatorId);
}

export async function createQuestionableSegmentation(
    globalContext: GlobalContext,
    segmentationContext: SegmentationContext,
    image: AbstractImage,
    axis: number,
    feature: FeatureGET,
    subtaskId?: number,
) {
    const creatorId = globalContext.user.id;
    await runCreate(async () => {
        const segmentation = await createSegmentationFrom(
            image,
            feature.id,
            "DualBitMask",
            "R8UI",
            0.5,
            axis,
            subtaskId,
        );
        activateCreated(segmentationContext, segmentation, creatorId);
    });
}

export async function createSegmentationFromDialog(
    globalContext: GlobalContext,
    segmentationContext: SegmentationContext,
    params: {
        image: AbstractImage;
        axis: number;
        feature: FeatureGET;
        subtaskId?: number;
        type: SegmentationTypeChoice;
        mode: CreateSegmentationDialogMode;
        box?: ImageBox;
        segWidth: number;
        segHeight: number;
    },
) {
    const {
        image,
        axis,
        feature,
        subtaskId,
        type,
        mode,
        box,
        segWidth,
        segHeight,
    } = params;

    const creatorId = globalContext.user.id;

    if (isMultiSegmentationType(type)) {
        await createMultiFeatureSegmentation(
            segmentationContext,
            image,
            axis,
            feature.id,
            type,
            creatorId,
        );
        return;
    }

    const w = Math.max(1, Math.round(segWidth));
    const h = Math.max(1, Math.round(segHeight));
    const depth = image.depth;

    let options: Parameters<typeof createSegmentationFrom>[7] | undefined;

    if (mode === "region" && box) {
        options = {
            shape: { depth, height: h, width: w },
            image_projection_matrix: projectionMatrixFromBox(box, w, h),
        };
    }

    await runCreate(async () => {
        const segmentation = await createSegmentationFrom(
            image,
            feature.id,
            dataRepresentationForType(type),
            dataTypeForType(type),
            0.5,
            axis,
            subtaskId,
            options,
        );
        activateCreated(segmentationContext, segmentation, creatorId);
    });
}

export async function createMultiFeatureSegmentation(
    segmentationContext: SegmentationContext,
    image: AbstractImage,
    axis: number,
    featureId: number,
    dataRepresentation: "MultiLabel" | "MultiClass",
    creatorId: number,
) {
    await runCreate(async () => {
        const segmentation = await createSegmentationFrom(
            image,
            featureId,
            dataRepresentation,
            "R8UI",
            0.5,
            axis,
        );
        activateCreated(segmentationContext, segmentation, creatorId);
    });
}

// Callers show the failure: the section notice for a quick create, the modal's error for Advanced.
async function runCreate(fn: () => Promise<void>) {
    try {
        await fn();
    } catch (err) {
        console.error(err);
        throw err;
    }
}

export function defaultRegionSize(box: ImageBox) {
    return {
        width: imageBoxWidth(box),
        height: imageBoxHeight(box),
    };
}
