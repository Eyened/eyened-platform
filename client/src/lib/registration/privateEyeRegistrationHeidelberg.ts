import type { Instance } from "$lib/datamodel/instance";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { CirclePhotoLocator, LinePhotoLocator, type PhotoLocator } from "./photoLocators";

function getSourceID(instance: Instance) {
    return instance.datasetIdentifier.split('/').pop()!;
}
export function getPrivateEyeRegistrationHeidelberg(image: AbstractImage): PhotoLocator[] {
    const { instance, meta } = image;
    if (!meta || !meta.images || !meta.images.images || !meta.images.images.length) return [];
    const source_id = getSourceID(instance);
    if (!source_id.startsWith('OCT')) return [];

    const oct_image_meta = meta.images.images.find((image: any) => image.source_id == source_id);
    if (!oct_image_meta) return [];

    const source_id_nr = source_id.split('-').pop();

    const linked_image = meta.images.images.find((image: any) => {
        if (image.source_id === source_id) return false;
        if (image.source_id.split('-').pop() !== source_id_nr) return false;
        return true;
    });
    if (!linked_image) return [];

    const enfaceInstance = instance.series.instances.find(instance => getSourceID(instance) == linked_image.source_id);
    if (!enfaceInstance) return [];
    const enfaceID = `${enfaceInstance.id}`;
    const octID = `${instance.id}`;

    const photoLocators: PhotoLocator[] = oct_image_meta.contents.map(
        (item: { photo_locations: any[] }, index: number) => {
            const locator = item.photo_locations[0];
            const { start, end, centre, radius, start_angle } = locator;
            if (start && end) {
                return new LinePhotoLocator(enfaceID, octID, start, end, index, instance.columns);
            }
            if (centre && radius) {
                return new CirclePhotoLocator(enfaceID, octID, centre, radius, start_angle, index, instance.columns);
            }
            return null;
        }
    ).filter(Boolean);
    return photoLocators;
}