import type { Datatype } from "$lib/datamodel/segmentation.svelte";

import type { GlobalContext } from "$lib/data/globalContext.svelte";
import type { DataRepresentation, SimpleDataRepresentation } from "$lib/datamodel/segmentation.svelte";
import { Segmentation } from "$lib/datamodel/segmentation.svelte";
import { NPYArray } from "$lib/utils/npy_loader";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { DrawingArray } from "$lib/webgl/mask.svelte";
import { convert } from "$lib/webgl/segmentationConverter";
import type { SegmentationItem } from "$lib/webgl/segmentationItem";
import type { ModelSegmentationGET, SegmentationGET } from "../../../types/openapi_types";

export const types: Record<"Q" | "B" | "P", SimpleDataRepresentation> = {
    Q: "DualBitMask",
    B: "Binary",
    P: "Probability",
};
function createArray(
    shape: [number, number, number],
    dataType: Datatype,
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
    segmentation: Segmentation,
    dataRepresentation: DataRepresentation,
    array: NPYArray,
    image: AbstractImage
) {
    for (let i = 0; i < indices.length; i++) {
        const mask = segmentationItem.getMask(indices[i]);
        if (mask) {
            const data = mask.exportData();
            const threshold = 255 * (segmentation.threshold ?? 0.5);
            const dataConverted = convert(
                data,
                segmentation.dataRepresentation as SimpleDataRepresentation,
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
    segmentation: SegmentationGET | ModelSegmentationGET, segmentationItem: SegmentationItem,
    image: AbstractImage,
    viewerContext: ViewerContext,
    duplicateVolume: boolean,
    type: "Q" | "B" | "P",
    creatorId: number) {
    globalContext.dialogue = `Duplicating segmentation ${segmentation.id}...`;

    let dataRepresentation: DataRepresentation;
    if (
        segmentation.data_representation == "MultiClass" ||
        segmentation.data_representation == "MultiLabel"
    ) {
        // same as original annotation type
        dataRepresentation = segmentation.data_representation;
    } else {
        // new annotation can be of different type
        dataRepresentation = types[type];
    }

    let dataType = segmentation.data_type;
    if (dataRepresentation == "Probability") {
        dataType = "R8";
    }
    const item = {
        ...segmentation,
        dataRepresentation,
        dataType,
        // properties that need to be mentioned explicitly, because they're marked with $state and hence not enumerable
        referenceId: segmentation.reference_segmentation_id,
        scanIndices: segmentation.scan_indices,
        threshold: segmentation.threshold,

        // overwrite creatorId to current user
        creatorId: creatorId,
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
        item.scanIndices = [scanNr];
    }

    const array = createArray(
        [depth, image.height, image.width],
        segmentation.data_type,
    );
    if (image.image_id.endsWith("proj")) {
        array.shape = [image.height, 1, image.width];
    }

    if (item.scanIndices) {
        // sparse volume
        copyMaskData(
            item.scanIndices,
            segmentationItem,
            segmentation,
            dataRepresentation,
            array,
            image
        );
    } else {
        // full volume
        const indices = Array.from({ length: depth }, (_, i) => i);
        copyMaskData(
            indices,
            segmentationItem,
            segmentation,
            dataRepresentation,
            array,
            image
        );
    }
    const newSegmentation = await Segmentation.create(item, array);
    console.log("newSegmentation", newSegmentation);

    globalContext.dialogue = null;
}