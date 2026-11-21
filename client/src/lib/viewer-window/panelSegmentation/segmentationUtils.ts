import type {
    ModelSegmentationGET,
    SegmentationGET,
} from "../../../types/openapi_types";

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

/** "Mine" for the user's own segmentation, else its creator's name. */
export function authorName(
    segmentation: { creator: { id: number; name: string } },
    me: number,
): string {
    return segmentation.creator.id === me ? "Mine" : segmentation.creator.name;
}

/** The Layers group a segmentation is listed under: "AI", "Mine" or its creator's name. */
export function groupTitle(segmentation: Segmentation, me: number): string {
    return segmentation.annotation_type === "model_segmentation"
        ? "AI"
        : authorName(segmentation as SegmentationGET, me);
}

export type SegmentationGroup = {
    key: string;
    title: string;
    rows: Segmentation[];
};

/** Layers' segmentation groups: AI, Mine, then each other grader in the order they come. */
export function segmentationGroups(
    model: Segmentation[],
    grader: SegmentationGET[],
    me: number,
): SegmentationGroup[] {
    const result: SegmentationGroup[] = [];
    if (model.length > 0) result.push({ key: "ai", title: "AI", rows: model });
    const byCreator = groupByCreator(grader);
    const mine = byCreator.get(me);
    if (mine) result.push({ key: String(me), title: "Mine", rows: mine });
    for (const [creatorId, rows] of byCreator)
        if (creatorId !== me)
            result.push({
                key: String(creatorId),
                title: groupTitle(rows[0], me),
                rows,
            });
    return result;
}

/**
 * Orders segmentations in the same order as the Segmentations section:
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
    for (const [
        creatorId,
        segmentations,
    ] of segmentationsByCreators.entries()) {
        if (creatorId !== userId) {
            result.push(...segmentations);
        }
    }

    return result;
}

const LETTERS: Record<string, string> = {
    Binary: "B",
    DualBitMask: "Q",
    Probability: "P",
    MultiClass: "MC",
    MultiLabel: "ML",
};

/** The short type shown on a row's badge and in the pickers. */
export function representationLetter(representation: string): string {
    return LETTERS[representation] ?? representation;
}
