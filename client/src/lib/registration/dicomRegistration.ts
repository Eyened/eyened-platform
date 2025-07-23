import { getInstanceBySOPInstanceUID, } from "$lib/datamodel/instance.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { LinePhotoLocator, type PhotoLocator } from "./photoLocators";

export function getDicomRegistration(image: AbstractImage): PhotoLocator[] {

    const { instance, meta } = image;
    if (!meta || !Array.isArray(meta.x52009230)) return [];

    const width = instance.columns;

    const octID = `${instance.id}`;
    const result: PhotoLocator[] = [];
    for (const [index, frameGroup] of meta.x52009230.entries()) {
        const frameLocation = frameGroup.x00220031[0]; // Ophthalmic Frame Location Sequence

        if (frameLocation.x00220039 != "LINEAR") {
            console.log('Not implemented frameLocation:', frameLocation.x00220039);
            continue;
        }

        const ReferencedSOPInstanceUID = frameLocation.x00081155;

        const enfaceInstance = getInstanceBySOPInstanceUID(ReferencedSOPInstanceUID);
        if (!enfaceInstance) continue;

        const referenceCoordinatesStr = frameLocation.x00220032; // Reference Coordinates
        const [startY, startX, endY, endX] = referenceCoordinatesStr.split('/').map(Number);
        const start = { x: startX, y: startY };
        const end = { x: endX, y: endY };

        const enfaceID = `${enfaceInstance.id}`;

        const locator = new LinePhotoLocator(enfaceID, octID, start, end, index, width);
        result.push(locator);
    }

    return result;
}