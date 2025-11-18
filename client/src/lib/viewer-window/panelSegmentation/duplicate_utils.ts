import type { GlobalContext } from "$lib/data/globalContext.svelte";
import type { SegmentationDataRepresentation, SegmentationDataType } from "../../../types/openapi_types";
import { NPYArray } from "$lib/utils/npy_loader";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { DrawingArray } from "$lib/webgl/mask.svelte";
import { convert } from "$lib/webgl/segmentationConverter";
import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
import type { ModelSegmentationGET, SegmentationGET } from "../../../types/openapi_types";
import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
import { createSegmentation } from "$lib/data/api";

// SimpleDataRepresentation is a subset of SegmentationDataRepresentation
type SimpleDataRepresentation = 'Binary' | 'DualBitMask' | 'Probability';
type DataRepresentation = SegmentationDataRepresentation;

export const types: Record<"Q" | "B" | "P", SimpleDataRepresentation> = {
    Q: "DualBitMask",
    B: "Binary",
    P: "Probability",
};
function createArray(
    shape: [number, number, number],
    dataType: SegmentationDataType,
): NPYArray {
    const n = shape[0] * shape[1] * shape[2];
    let a: DrawingArray;
    if (dataType == "R8UI" || dataType == "R8") {
        a = new Uint8Array(n);
    } else if (dataType == "R16UI") {
        a = new Uint16Array(n);
    } else if (dataType == "R32UI") {
        a = new Uint32Array(n);
    } else if (dataType == "R32F") {
        a = new Float32Array(n);
    } else {
        throw new Error(`Unsupported data type: ${dataType}`);
    }
    return new NPYArray(a, shape, false);
}

function copyMaskData(
    indices: number[],
    segmentationItem: SegmentationItem,
    segmentation: SegmentationGET | ModelSegmentationGET,
    dataRepresentation: SegmentationDataRepresentation,
    array: NPYArray,
    image: AbstractImage,
    originalThreshold: number
) {
    for (let i = 0; i < indices.length; i++) {
        const mask = segmentationItem.getMask(indices[i]);
        if (mask) {
            const data = mask.exportData();
            const threshold = 255 * originalThreshold;
            const dataConverted = convert(
                data,
                segmentation.data_representation as SimpleDataRepresentation,
                dataRepresentation as SimpleDataRepresentation,
                threshold,
            );
            array.data.set(
                dataConverted,
                i * image.height * image.width,
            );
        }
    }
}

export async function duplicate(globalContext: GlobalContext,
    segmentation: SegmentationGET | ModelSegmentationGET,
    segmentationItem: SegmentationItem,
    image: AbstractImage,
    viewerContext: ViewerContext,
    duplicateVolume: boolean,
    type: "Q" | "B" | "P",
    originalThreshold: number,
    newThreshold: number, 
    taskContext?: TaskContext) {
    globalContext.dialogue = `Duplicating segmentation ${segmentation.id}...`;

    let data_representation: SegmentationDataRepresentation;
    if (
        segmentation.data_representation == "MultiClass" ||
        segmentation.data_representation == "MultiLabel"
    ) {
        // same as original annotation type
        data_representation = segmentation.data_representation;
    } else {
        // new annotation can be of different type
        data_representation = types[type];
    }

    let data_type = segmentation.data_type;
    if (data_representation == "Probability") {
        data_type = "R8";
    }
    const item = {
        ...segmentation,
        threshold: newThreshold,
        feature_id: segmentation.feature.id,        
        data_representation,
        data_type,
        subtask_id: taskContext?.subTask.id ?? null,
    };

    const scanNr = viewerContext.index;

    let depth = 1;
    if (duplicateVolume) {
        if (segmentation.scan_indices) {
            // only upload the data for active scan indices
            depth = segmentation.scan_indices.length;
        } else {
            // upload the full volume
            depth = image.depth;
        }
    } else if (image.is3D) {
        // only duplicate the current scan
        item.scan_indices = [scanNr];
    }

    const array = createArray(
        [depth, image.height, image.width],
        segmentation.data_type,
    );
    if (image.image_id.endsWith("proj")) {
        array.shape = [image.height, 1, image.width];
    }

    if (item.scan_indices) {
        // sparse volume
        copyMaskData(
            item.scan_indices,
            segmentationItem,
            segmentation,
            data_representation,
            array,
            image,
            originalThreshold
        );
    } else {
        // full volume
        const indices = Array.from({ length: depth }, (_, i) => i);
        copyMaskData(
            indices,
            segmentationItem,
            segmentation,
            data_representation,
            array,
            image,
            originalThreshold
        );
    }
    const newSegmentation = await createSegmentation(item, array);

    globalContext.dialogue = null;
    return newSegmentation;
}