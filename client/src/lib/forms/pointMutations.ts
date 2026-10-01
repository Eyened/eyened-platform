import type { ImagePoint, PointCardinality, PointList } from "./pointSchema";
import type { Position2D } from "$lib/types";

export type PlacePointOptions = {
    /**
     * OCT volume B-scan index (number), or `null` for enface `*_proj`.
     * Omit the option entirely for plain 2D images (no index property).
     */
    index?: number | null;
    /**
     * String enums on the point. A required one is set to its first value
     * when the written point does not already have a valid value.
     */
    enumExtras?: readonly {
        key: string;
        values: readonly string[];
        required?: boolean;
    }[];
};

function withRequiredEnumDefaults(
    point: ImagePoint,
    options?: PlacePointOptions,
): ImagePoint {
    const extras = options?.enumExtras;
    if (!extras?.length) return point;
    let next = point;
    for (const extra of extras) {
        if (!extra.required || extra.values.length === 0) continue;
        const current = next[extra.key];
        if (typeof current === "string" && extra.values.includes(current)) {
            continue;
        }
        next = { ...next, [extra.key]: extra.values[0]! };
    }
    return next;
}

/** Keep a valid enum already stored on a point being rewritten in place. */
function carryEnumExtras(
    existing: ImagePoint | null | undefined,
    point: ImagePoint,
    options?: PlacePointOptions,
): ImagePoint {
    const extras = options?.enumExtras;
    if (!existing || !extras?.length) return point;
    let next = point;
    for (const extra of extras) {
        const current = existing[extra.key];
        if (typeof current === "string" && extra.values.includes(current)) {
            next = { ...next, [extra.key]: current };
        }
    }
    return next;
}

export function placePoint(
    points: PointList,
    position: Position2D,
    cardinality: PointCardinality,
    sparse: boolean,
    options?: PlacePointOptions,
): PointList {
    const next: ImagePoint = { x: position.x, y: position.y };
    if (options && "index" in options) {
        next.index = options.index;
    }

    if (cardinality === "single") {
        const prev = points.find((p) => p != null);
        // Keep non-spatial extras (note, severity, …) when replacing the one point.
        const merged: ImagePoint = prev ? { ...prev, ...next } : next;
        // Plain 2D omits index options — drop a stale volume index so the
        // marker stays visible (visibleOnSlice rejects numeric index on 2D).
        if (!options || !("index" in options)) {
            const { index: _drop, ...rest } = merged;
            return [withRequiredEnumDefaults(rest, options)];
        }
        return [withRequiredEnumDefaults(merged, options)];
    }

    const copy = [...points];
    if (sparse) {
        for (let i = 0; i <= copy.length; i++) {
            if (!copy[i]) {
                copy[i] = withRequiredEnumDefaults(next, options);
                return copy;
            }
        }
    }
    copy.push(withRequiredEnumDefaults(next, options));
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
    const existing = copy[index];
    copy[index] = withRequiredEnumDefaults(
        carryEnumExtras(existing, next, options),
        options,
    );
    return copy;
}

export function deletePointAt(
    points: PointList,
    index: number,
    sparse: boolean,
): PointList {
    const copy = [...points];
    if (index < 0 || index >= copy.length) return copy;

    if (sparse) {
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
