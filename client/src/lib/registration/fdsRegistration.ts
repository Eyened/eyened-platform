import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { PhotoLocator } from "./photoLocators";
import { createPhotoLocator, parsePhotoLocatorItem } from "./parsePhotoLocator";

export function getFdsRegistration(image: AbstractImage): PhotoLocator[] {
    const { instance } = image;
    const octID = `${instance.id}`;
    const photoLocators = instance.attrs?.PhotoLocators;

    if (!Array.isArray(photoLocators)) {
        return [];
    }

    return photoLocators.flatMap((raw) => {
        const item = parsePhotoLocatorItem(raw);
        if (!item) {
            return [];
        }
        const locator = createPhotoLocator(item, octID, image.width);
        return locator ? [locator] : [];
    });
}
