import type { ImagePoint, PointCardinality, PointList } from "./pointSchema";
import type { Position2D } from "$lib/types";

export type PlacePointOptions = {
    /**
     * OCT volume B-scan index (number), or `null` for enface `*_proj`.
     * Omit the option entirely for plain 2D images (no index property).
     */
    index?: number | null;
};

export function placePoint(
    points: PointList,
    position: Position2D,
    cardinality: PointCardinality,
    registrationMode: boolean,
    options?: PlacePointOptions,
): PointList {
    const next: ImagePoint = { x: position.x, y: position.y };
    if (options && "index" in options) {
        next.index = options.index;
    }

    if (cardinality === "single") {
        return [next];
    }

    const copy = [...points];
    if (registrationMode) {
        for (let i = 0; i <= copy.length; i++) {
            if (!copy[i]) {
                copy[i] = next;
                return copy;
            }
        }
    }
    copy.push(next);
    return copy;
}

export function placePointAt(
    points: PointList,
    index: number,
    position: Position2D,
    options?: PlacePointOptions,
): PointList {
    if (index < 0) return [...points];
    const next: ImagePoint = { x: position.x, y: position.y };
    if (options && "index" in options) {
        next.index = options.index;
    }
    const copy = [...points];
    while (copy.length <= index) copy.push(null);
    copy[index] = next;
    return copy;
}

export function deletePointAt(
    points: PointList,
    index: number,
    registrationMode: boolean,
): PointList {
    const copy = [...points];
    if (index < 0 || index >= copy.length) return copy;

    if (registrationMode) {
        if (index === copy.length - 1) {
            copy.splice(index, 1);
        } else {
            copy[index] = null;
        }
        return copy;
    }

    copy.splice(index, 1);
    return copy;
}

export function movePointAt(
    points: PointList,
    index: number,
    position: Position2D,
): PointList {
    const copy = [...points];
    const existing = copy[index];
    if (!existing) return copy;
    copy[index] = { ...existing, x: position.x, y: position.y };
    return copy;
}

export function cycleEnumExtra(
    point: ImagePoint,
    key: string,
    values: readonly string[],
): ImagePoint {
    if (values.length === 0) return point;
    const current = point[key];
    const idx = typeof current === "string" ? values.indexOf(current) : -1;
    const next = values[(idx + 1) % values.length]!;
    return { ...point, [key]: next };
}
