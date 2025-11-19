import type { ModelSegmentationGET, SegmentationGET } from "../../../types/openapi_types";

export type Segmentation = SegmentationGET | ModelSegmentationGET;
/**
 * Groups segmentations by creator ID
 */
export function groupByCreator(
    segmentations: SegmentationGET[],
): Map<number, SegmentationGET[]> {
    const map = new Map<number, SegmentationGET[]>();
    for (const segmentation of segmentations) {
        const creatorId = segmentation.creator.id;
        if (!map.has(creatorId)) {
            map.set(creatorId, []);
        }
        map.get(creatorId)!.push(segmentation);
    }
    return map;
}

/**
 * Orders segmentations in the same order as PanelSegmentation:
 * 1. Model segmentations first
 * 2. User's own grader segmentations (grouped by creator)
 * 3. Other graders' segmentations (grouped by creator)
 * 
 * Returns a flat array maintaining the grouping order.
 */
export function orderSegmentationsByCreator(
    modelSegmentations: ModelSegmentationGET[],
    graderSegmentations: SegmentationGET[],
    userId: number,
): Segmentation[] {
    const result: Segmentation[] = [];

    // 1. Model segmentations first
    result.push(...modelSegmentations);

    // 2. Group grader segmentations by creator
    const segmentationsByCreators = groupByCreator(graderSegmentations);

    // 3. User's own segmentations first
    if (segmentationsByCreators.has(userId)) {
        result.push(...segmentationsByCreators.get(userId)!);
    }

    // 4. Other graders' segmentations
    for (const [creatorId, segmentations] of segmentationsByCreators.entries()) {
        if (creatorId !== userId) {
            result.push(...segmentations);
        }
    }

    return result;
}