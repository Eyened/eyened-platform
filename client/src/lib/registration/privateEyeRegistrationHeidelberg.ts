import { instances } from "$lib/data";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { ImageGET } from "../../types/openapi_types";
import type { PhotoLocator } from "./photoLocators";
import {
    createPhotoLocator,
    parseHeidelbergPhotoLocator,
} from "./parsePhotoLocator";

type HeidelbergImageEntry = {
    source_id: string;
    contents?: { photo_locations: unknown[] }[];
};

function getHeidelbergImages(
    meta: Record<string, unknown> | undefined,
): HeidelbergImageEntry[] | undefined {
    const images = meta?.images as
        | { images?: HeidelbergImageEntry[] }
        | undefined;
    return images?.images;
}

function getSourceID(instance: ImageGET) {
    return instance.data_source_id ?? "";
}
export function getPrivateEyeRegistrationHeidelberg(
    image: AbstractImage,
): PhotoLocator[] {
    const { instance, meta } = image;
    const heidelbergImages = getHeidelbergImages(meta);
    if (!heidelbergImages?.length) return [];
    const source_id = getSourceID(instance);
    if (!source_id.startsWith("OCT")) return [];

    const oct_image_meta = heidelbergImages.find(
        (entry) => entry.source_id == source_id,
    );
    if (!oct_image_meta) return [];

    const source_id_nr = source_id.split("-").pop();

    const linked_image = heidelbergImages.find((entry) => {
        if (entry.source_id === source_id) return false;
        if (entry.source_id.split("-").pop() !== source_id_nr) return false;
        return true;
    });
    if (!linked_image) return [];

    const instance_series = instances.filter(
        (i) => i.series.id == instance.series.id,
    );
    const enfaceInstance = instance_series.find(
        (i) => getSourceID(i) == linked_image.source_id,
    );
    if (!enfaceInstance) return [];
    const enfaceID = `${enfaceInstance.id}`;
    const octID = `${instance.id}`;

    return (oct_image_meta.contents ?? []).flatMap(
        (item: { photo_locations: unknown[] }, index: number) => {
            const locator = item.photo_locations?.[0];
            const parsed = parseHeidelbergPhotoLocator(
                locator,
                enfaceID,
                index,
            );
            if (!parsed) {
                return [];
            }
            const runtime = createPhotoLocator(parsed, octID, instance.columns);
            return runtime ? [runtime] : [];
        },
    );
}
