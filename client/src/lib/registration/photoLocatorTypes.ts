export type Point2D = {
    x: number;
    y: number;
};

/** PhotoLocators attribute / API JSON shape for a line locator. */
export type LinePhotoLocator = {
    type: 'LinePhotoLocator';
    image_id: string;
    index: number;
    start: Point2D;
    end: Point2D;
};

/** PhotoLocators attribute / API JSON shape for a circle locator. */
export type CirclePhotoLocator = {
    type: 'CirclePhotoLocator';
    image_id: string;
    index: number;
    center: Point2D;
    radius: number;
    start_angle: number;
};

export type PhotoLocatorItem = LinePhotoLocator | CirclePhotoLocator;

/** Partial Heidelberg meta locator (type/image_id/index inferred at parse time). */
export type HeidelbergPhotoLocatorInput = {
    start?: Point2D;
    end?: Point2D;
    center?: Point2D;
    centre?: Point2D;
    radius?: number;
    start_angle?: number;
};
