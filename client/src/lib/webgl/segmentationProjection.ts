import { Matrix } from "$lib/matrix";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type {
    ModelSegmentationGET,
    SegmentationGET,
} from "../../types/openapi_types";

export type SegmentationWithProjection = SegmentationGET | ModelSegmentationGET;

export function segToImageMatrix(
    segmentation: SegmentationWithProjection,
): Matrix {
    const m = segmentation.image_projection_matrix;
    if (!m) {
        return Matrix.identity;
    }
    return Matrix.fromRows(m);
}

/** 2D plane width/height for mask textures and drawing (sparse_axis 0 / default). */
export function segmentationPlaneSize(
    segmentation: SegmentationWithProjection,
    image: { width: number; height: number; depth: number },
): { width: number; height: number } {
    const sparseAxis = segmentation.sparse_axis;
    if (sparseAxis == null || sparseAxis === undefined || sparseAxis === 0) {
        return { width: segmentation.width, height: segmentation.height };
    }
    if (sparseAxis === 1) {
        return { width: segmentation.width, height: segmentation.depth };
    }
    if (sparseAxis === 2) {
        return { width: segmentation.depth, height: segmentation.height };
    }
    return { width: image.width, height: image.height };
}

export function getSegmentationOverlayUniforms(
    viewerContext: ViewerContext,
    segmentation: SegmentationWithProjection,
) {
    const segToImage = segToImageMatrix(segmentation);
    const segmentationWebglTransform = viewerContext.scaleViewerMatrix.multiply(
        viewerContext.imageViewerTransform.multiply(segToImage),
    );
    const plane = segmentationPlaneSize(segmentation, viewerContext.image);

    return {
        u_transform: segmentationWebglTransform.asUniform,
        u_image_size: [plane.width, plane.height, 1],
    };
}
