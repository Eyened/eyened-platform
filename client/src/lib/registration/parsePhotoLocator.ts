import {
    CirclePhotoLocator as CirclePhotoLocatorModel,
    LinePhotoLocator as LinePhotoLocatorModel,
    type PhotoLocator,
} from "./photoLocators";
import type {
    CirclePhotoLocator,
    HeidelbergPhotoLocatorInput,
    LinePhotoLocator,
    PhotoLocatorItem,
    Point2D,
} from "./photoLocatorTypes";

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPoint2D(value: unknown): value is Point2D {
    return (
        isRecord(value) &&
        typeof value.x === "number" &&
        Number.isFinite(value.x) &&
        typeof value.y === "number" &&
        Number.isFinite(value.y)
    );
}

function readCenter(raw: Record<string, unknown>): {
    center: Point2D | null;
    usedLegacyCentre: boolean;
} {
    if (isPoint2D(raw.center)) {
        return { center: raw.center, usedLegacyCentre: false };
    }
    if (isPoint2D(raw.centre)) {
        return { center: raw.centre, usedLegacyCentre: true };
    }
    return { center: null, usedLegacyCentre: false };
}

function normalizeCircleFields(
    raw: Record<string, unknown>,
): Record<string, unknown> | null {
    const { center, usedLegacyCentre } = readCenter(raw);
    if (!center) {
        return null;
    }
    if (usedLegacyCentre) {
        console.warn("PhotoLocator: legacy field centre converted to center");
    }
    if (
        typeof raw.radius !== "number" ||
        !Number.isFinite(raw.radius) ||
        typeof raw.start_angle !== "number" ||
        !Number.isFinite(raw.start_angle)
    ) {
        return null;
    }
    return {
        ...raw,
        center,
        centre: undefined,
    };
}

function inferHeidelbergPhotoLocator(
    raw: HeidelbergPhotoLocatorInput,
    enfaceImageId: string,
    index: number,
): PhotoLocatorItem | null {
    if (isPoint2D(raw.start) && isPoint2D(raw.end)) {
        return {
            type: "LinePhotoLocator",
            image_id: enfaceImageId,
            index,
            start: raw.start,
            end: raw.end,
        };
    }

    const normalized = normalizeCircleFields(raw as Record<string, unknown>);
    if (!normalized) {
        return null;
    }

    const center = normalized.center as Point2D;
    return {
        type: "CirclePhotoLocator",
        image_id: enfaceImageId,
        index,
        center,
        radius: normalized.radius as number,
        start_angle: normalized.start_angle as number,
    };
}

export function parsePhotoLocatorItem(raw: unknown): PhotoLocatorItem | null {
    if (!isRecord(raw)) {
        console.warn("PhotoLocator: expected object, skipping entry");
        return null;
    }

    const locatorType = raw.type;
    if (locatorType === "LinePhotoLocator") {
        if (
            typeof raw.image_id !== "string" ||
            typeof raw.index !== "number" ||
            !Number.isInteger(raw.index) ||
            !isPoint2D(raw.start) ||
            !isPoint2D(raw.end)
        ) {
            console.warn(
                "PhotoLocator: invalid LinePhotoLocator entry, skipping",
            );
            return null;
        }
        return {
            type: "LinePhotoLocator",
            image_id: raw.image_id,
            index: raw.index,
            start: raw.start,
            end: raw.end,
        };
    }

    if (locatorType === "CirclePhotoLocator") {
        const normalized = normalizeCircleFields(raw);
        if (
            !normalized ||
            typeof raw.image_id !== "string" ||
            typeof raw.index !== "number" ||
            !Number.isInteger(raw.index)
        ) {
            console.warn(
                "PhotoLocator: invalid CirclePhotoLocator entry, skipping",
            );
            return null;
        }
        return {
            type: "CirclePhotoLocator",
            image_id: raw.image_id as string,
            index: raw.index as number,
            center: normalized.center as Point2D,
            radius: normalized.radius as number,
            start_angle: normalized.start_angle as number,
        };
    }

    console.warn(`PhotoLocator: unknown type ${String(locatorType)}, skipping`);
    return null;
}

export function parseHeidelbergPhotoLocator(
    raw: unknown,
    enfaceImageId: string,
    index: number,
): PhotoLocatorItem | null {
    if (!isRecord(raw)) {
        console.warn(
            "PhotoLocator: expected Heidelberg locator object, skipping",
        );
        return null;
    }
    const item = inferHeidelbergPhotoLocator(
        raw as HeidelbergPhotoLocatorInput,
        enfaceImageId,
        index,
    );
    if (!item) {
        console.warn(
            "PhotoLocator: invalid Heidelberg locator entry, skipping",
        );
    }
    return item;
}

export function createPhotoLocator(
    item: PhotoLocatorItem,
    octID: string,
    width: number,
): PhotoLocator | null {
    if (item.type === "LinePhotoLocator") {
        return linePhotoLocatorFromItem(item, octID, width);
    }
    return circlePhotoLocatorFromItem(item, octID, width);
}

function linePhotoLocatorFromItem(
    item: LinePhotoLocator,
    octID: string,
    width: number,
): LinePhotoLocatorModel {
    return new LinePhotoLocatorModel(
        item.image_id,
        octID,
        item.start,
        item.end,
        item.index,
        width,
    );
}

function circlePhotoLocatorFromItem(
    item: CirclePhotoLocator,
    octID: string,
    width: number,
): CirclePhotoLocatorModel {
    return new CirclePhotoLocatorModel(
        item.image_id,
        octID,
        item.center,
        item.radius,
        item.start_angle,
        item.index,
        width,
    );
}
