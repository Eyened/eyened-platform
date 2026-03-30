// import { getInstanceByDataSourceId } from "$lib/data";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { CirclePhotoLocator, LinePhotoLocator, type PhotoLocator } from "./photoLocators";


export function getFdsRegistration(image: AbstractImage): PhotoLocator[] {
    const { instance, meta } = image;
    const octID = `${instance.id}`;

    if (instance.attrs?.PhotoLocators) {
        const parsePhotoLocator = (photoLocator: any): PhotoLocator => {
            if (photoLocator.type === 'LinePhotoLocator') {
                const enfaceImageId = photoLocator.image_id;
                const start = photoLocator.start;
                const end = photoLocator.end;
                const index = photoLocator.index;
                const width = image.width;
                return new LinePhotoLocator(enfaceImageId, octID, start, end, index, width);
            }
            if (photoLocator.type === 'CirclePhotoLocator') {
                const enfaceImageId = photoLocator.image_id;
                const centre = photoLocator.centre;
                const radius = photoLocator.radius;
                const start_angle = photoLocator.start_angle;
                const index = photoLocator.index;
                const width = image.width;
                return new CirclePhotoLocator(enfaceImageId, octID, centre, radius, start_angle, index, width);
            }
            throw new Error(`Unknown photo locator type: ${photoLocator.type}`);
        }
        return instance.attrs.PhotoLocators.map(parsePhotoLocator);
    }

    return [];
    // below: outdated

    // if (!instance || !meta?.registration?.top_left || !meta?.registration?.bottom_right || !meta?.oct_shape) {
    //     return [];
    // }
    // const sourceId = instance.data_source_id ?? '';

    // const enfaceInstance = sourceId ? getInstanceByDataSourceId(sourceId) : undefined;

    // if (!enfaceInstance) {
    //     return [];
    // }
    // const enfaceID = `${enfaceInstance.id}`;

    // const { top_left, bottom_right } = meta.registration;

    // if (instance.scan.mode == 'Circle-Scan') {
    //     // this is extracted wrongly from the fds files
    //     const [cx, cy] = top_left;
    //     const radius = bottom_right[0];
    //     const photoLocations = [
    //         new CirclePhotoLocator(enfaceID, octID, { x: cx, y: cy }, radius, Math.PI, 0, instance.columns)
    //     ]
    //     return photoLocations;
    // }

    // const { oct_shape } = meta;
    // const [n_scans, h, w] = oct_shape;
    // const [x0, y0] = top_left;
    // const [x1, y1] = bottom_right;



    // const photoLocations: LinePhotoLocator[] = Array.from({ length: n_scans }, (_, i) => {
    //     const r = i / n_scans;
    //     if (instance.scan.mode == 'Vertical 3DSCAN') {
    //         const start = { x: x0 + r * (x1 - x0), y: y0 };
    //         const end = { x: x0 + r * (x1 - x0), y: y1 };
    //         return new LinePhotoLocator(enfaceID, octID, start, end, i, w);
    //     } else {
    //         const start = { x: x0, y: y0 + r * (y1 - y0) };
    //         const end = { x: x1, y: y0 + r * (y1 - y0) };
    //         return new LinePhotoLocator(enfaceID, octID, start, end, i, w);
    //     }
    // });

    // return photoLocations;
}