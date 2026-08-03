import type { JSONSchema } from "./schemaType";

export const EYENED_KEYPOINT_WIDGET = "keypoint" as const;

export type ImagePoint = {
    x: number;
    y: number;
    /**
     * OCT volume: B-scan slice number.
     * Enface `*_proj`: explicitly `null`.
     * Plain 2D: omitted.
     */
    index?: number | null;
} & Record<string, unknown>;
export type PointCardinality = "single" | "list";
/** Where the tool reads/writes relative to the field value. */
export type PointAddressing = "bare" | "byImage";
/**
 * Derived from whether the point object schema declares an `index` property.
 * - `enface2d`: plain {x,y} — fundus / enface / `*_proj` only (not OCT B-scan volumes).
 * - `oct`: may carry `index` (B-scan) or `index: null` (`*_proj`); also ok on plain 2D.
 */
export type PointCoordinateSpace = "enface2d" | "oct";
export type PointList = (ImagePoint | null)[];

export type PointSchemaAnalysis = {
    cardinality: PointCardinality;
    addressing: PointAddressing;
    /** Schema for one point object (items or the object itself). */
    pointObjectSchema: JSONSchema;
    /** List items may be null — mid-delete leaves holes; empty click fills first null. */
    sparse: boolean;
    enumExtras: { key: string; values: readonly string[] }[];
    coordinateSpace: PointCoordinateSpace;
};

/** Whether the current viewer image is compatible with this field's coordinate space. */
export function canPlaceOnViewer(
    coordinateSpace: PointCoordinateSpace,
    image: { is3D: boolean },
): { ok: true } | { ok: false; message: string } {
    if (coordinateSpace === "enface2d" && image.is3D) {
        return {
            ok: false,
            message:
                "This point field is 2D-only — switch to a fundus or enface image (not an OCT B-scan volume).",
        };
    }
    return { ok: true };
}

export function isPointWidget(schema: JSONSchema): boolean {
    return schema["x-eyened-widget"] === EYENED_KEYPOINT_WIDGET;
}

function schemaType(schema: JSONSchema | undefined): string | undefined {
    if (!schema?.type) return undefined;
    return Array.isArray(schema.type) ? schema.type[0] : schema.type;
}

function isPointObjectSchema(schema: JSONSchema | undefined): boolean {
    if (!schema) return false;
    if (schemaType(schema) === "object") {
        const props = schema.properties;
        return !!(props?.x && props?.y);
    }
    return false;
}

/** True if items schema allows null (oneOf/anyOf with null, or type null). */
function itemsAllowNull(items: JSONSchema | undefined): boolean {
    if (!items) return false;
    if (schemaType(items) === "null") return true;
    const alts = items.oneOf ?? items.anyOf;
    if (!alts) return false;
    return alts.some((option) => schemaType(option) === "null");
}

/** Unwrap oneOf/anyOf that pairs a point object with null (sparse lists). */
function unwrapPointItemSchema(
    schema: JSONSchema | undefined,
): JSONSchema | null {
    if (!schema) return null;
    if (isPointObjectSchema(schema)) return schema;
    const alts = schema.oneOf ?? schema.anyOf;
    if (alts) {
        for (const option of alts) {
            if (isPointObjectSchema(option)) return option;
        }
    }
    return null;
}

function enumExtrasFromPointSchema(
    pointObjectSchema: JSONSchema,
): { key: string; values: readonly string[] }[] {
    const extras: { key: string; values: readonly string[] }[] = [];
    const props = pointObjectSchema.properties ?? {};
    for (const [key, prop] of Object.entries(props)) {
        if (key === "x" || key === "y") continue;
        const values = prop.enum;
        if (
            Array.isArray(values) &&
            values.length > 0 &&
            values.every((v) => typeof v === "string")
        ) {
            extras.push({ key, values: values as readonly string[] });
        }
    }
    return extras;
}

/**
 * Classify a keypoint-widget field schema from shape alone.
 * Returns null if the widget marker is present but the shape is not point-like.
 */
export function analyzePointSchema(
    schema: JSONSchema,
): PointSchemaAnalysis | null {
    if (!isPointWidget(schema)) return null;

    let cardinality: PointCardinality;
    let addressing: PointAddressing = "bare";
    let sparse = false;
    let pointObjectSchema: JSONSchema | null;
    let itemsSchema: JSONSchema | undefined;

    const t = schemaType(schema);
    const additional = schema.additionalProperties;

    if (additional && typeof additional === "object") {
        addressing = "byImage";
        const addType = schemaType(additional);
        if (addType === "array") {
            cardinality = "list";
            itemsSchema = additional.items;
            pointObjectSchema = unwrapPointItemSchema(itemsSchema);
            sparse = itemsAllowNull(itemsSchema);
        } else if (isPointObjectSchema(additional)) {
            cardinality = "single";
            pointObjectSchema = additional;
        } else {
            return null;
        }
    } else if (t === "array") {
        cardinality = "list";
        itemsSchema = schema.items;
        pointObjectSchema = unwrapPointItemSchema(itemsSchema);
        sparse = itemsAllowNull(itemsSchema);
    } else if (isPointObjectSchema(schema)) {
        cardinality = "single";
        pointObjectSchema = schema;
    } else {
        return null;
    }

    if (!pointObjectSchema) return null;

    const coordinateSpace: PointCoordinateSpace =
        pointObjectSchema.properties?.index !== undefined ? "oct" : "enface2d";

    return {
        cardinality,
        addressing,
        pointObjectSchema,
        sparse,
        enumExtras: enumExtrasFromPointSchema(pointObjectSchema),
        coordinateSpace,
    };
}

function isImagePoint(value: unknown): value is ImagePoint {
    return (
        typeof value === "object" &&
        value !== null &&
        typeof (value as ImagePoint).x === "number" &&
        typeof (value as ImagePoint).y === "number"
    );
}

function normalizeList(value: unknown): PointList {
    if (!Array.isArray(value)) return [];
    return value.map((item) =>
        isImagePoint(item) ? item : item === null ? null : null,
    );
}

/** Always returns an array (0–1 elements for single). Preserves null entries when sparse. */
export function getPointsForImage(
    fieldValue: unknown,
    publicId: string,
    analysis: PointSchemaAnalysis,
): PointList {
    if (!analysis) return [];
    if (analysis.addressing === "bare") {
        if (analysis.cardinality === "single") {
            return isImagePoint(fieldValue) ? [fieldValue] : [];
        }
        return normalizeList(fieldValue);
    }

    const map =
        typeof fieldValue === "object" && fieldValue !== null
            ? (fieldValue as Record<string, unknown>)
            : {};
    const entry = map[publicId];
    if (analysis.cardinality === "single") {
        return isImagePoint(entry) ? [entry] : [];
    }
    return normalizeList(entry);
}

/** Write points for the current image; returns the new field value (or undefined if cleared bare single). */
export function setPointsForImage(
    fieldValue: unknown,
    publicId: string,
    points: PointList,
    analysis: PointSchemaAnalysis,
): unknown {
    if (analysis.addressing === "bare") {
        if (analysis.cardinality === "single") {
            const first = points.find((p) => p != null);
            return first ?? undefined;
        }
        return points;
    }

    const map: Record<string, unknown> = {
        ...(typeof fieldValue === "object" && fieldValue !== null
            ? (fieldValue as Record<string, unknown>)
            : {}),
    };

    if (analysis.cardinality === "single") {
        const first = points.find((p) => p != null);
        if (first === undefined) {
            delete map[publicId];
        } else {
            map[publicId] = first;
        }
    } else {
        if (points.length === 0) {
            delete map[publicId];
        } else {
            map[publicId] = points;
        }
    }

    return map;
}
