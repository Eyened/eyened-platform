import { getInstanceByDataSetIdentifier } from "$lib/datamodel/instance.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { CirclePhotoLocator, LinePhotoLocator, type PhotoLocator } from "./photoLocators";

export function getFdsRegistration(image: AbstractImage): PhotoLocator[] {
    const { instance, meta } = image;
    if (!instance || !meta?.registration?.top_left || !meta?.registration?.bottom_right || !meta?.oct_shape) {
        return [];
    }
    const enfaceInstance = getInstanceByDataSetIdentifier(instance.datasetIdentifier.replace('.binary', '.png'));
    if (!enfaceInstance) {
        return [];
    }
    const enfaceID = `${enfaceInstance.id}`;
    const octID = `${instance.id}`;
    const { top_left, bottom_right } = meta.registration;

    if (instance.scan.mode == 'Circle-Scan') {
        // this is extracted wrongly from the fds files
        const [cx, cy] = top_left;
        const radius = bottom_right[0];
        const photoLocations = [
            new CirclePhotoLocator(enfaceID, octID, { x: cx, y: cy }, radius, Math.PI, 0, instance.columns)
        ]
        return photoLocations;
    }

    const { oct_shape } = meta;
    const [n_scans, h, w] = oct_shape;
    const [x0, y0] = top_left;
    const [x1, y1] = bottom_right;
    const photoLocations: LinePhotoLocator[] = Array.from({ length: n_scans }, (_, i) => {
        const r = i / n_scans;
        if (instance.scan.mode == 'Vertical 3DSCAN') {
            const start = { x: x0 + r * (x1 - x0), y: y0 };
            const end = { x: x0 + r * (x1 - x0), y: y1 };
            return new LinePhotoLocator(enfaceID, octID, start, end, i, w);
        } else {
            const start = { x: x0, y: y0 + r * (y1 - y0) };
            const end = { x: x1, y: y0 + r * (y1 - y0) };
            return new LinePhotoLocator(enfaceID, octID, start, end, i, w);
        }
    });
    return photoLocations;
}