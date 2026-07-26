import type { JSONSchema } from "./schemaType";

export const EYENED_POINT_WIDGET = "point" as const;

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
export type PointStorageMode = "bare" | "byPublicId";
export type PointList = (ImagePoint | null)[];

export type PointSchemaAnalysis = {
    cardinality: PointCardinality;
    storageMode: PointStorageMode;
    /** Schema for one point object (items or the object itself). */
    pointObjectSchema: JSONSchema;
    registrationMode: boolean;
    enumExtras: { key: string; values: readonly string[] }[];
};

export function isPointWidget(schema: JSONSchema): boolean {
    return schema["x-eyened-widget"] === EYENED_POINT_WIDGET;
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

/** Unwrap oneOf/anyOf that pairs a point object with null (registration). */
function unwrapPointItemSchema(schema: JSONSchema | undefined): JSONSchema | null {
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
 * Classify a point-widget field schema.
 * Returns null if the widget marker is present but the shape is not point-like.
 */
export function analyzePointSchema(
    schema: JSONSchema,
    entityType: string | null | undefined,
): PointSchemaAnalysis | null {
    if (!isPointWidget(schema)) return null;

    const storageMode: PointStorageMode =
        entityType === "ImageInstance" ? "bare" : "byPublicId";
    const registrationMode = schema["x-eyened-point-mode"] === "registration";

    let cardinality: PointCardinality;
    let pointObjectSchema: JSONSchema | null = null;

    const t = schemaType(schema);

    if (t === "array") {
        cardinality = "list";
        pointObjectSchema = unwrapPointItemSchema(schema.items);
    } else if (t === "object" || schema.additionalProperties) {
        const additional = schema.additionalProperties;
        if (additional && typeof additional === "object") {
            const addType = schemaType(additional);
            if (addType === "array") {
                cardinality = "list";
                pointObjectSchema = unwrapPointItemSchema(additional.items);
            } else if (isPointObjectSchema(additional)) {
                cardinality = "single";
                pointObjectSchema = additional;
            } else {
                return null;
            }
        } else if (isPointObjectSchema(schema)) {
            cardinality = "single";
            pointObjectSchema = schema;
        } else {
            return null;
        }
    } else {
        return null;
    }

    if (!pointObjectSchema) return null;

    return {
        cardinality,
        storageMode,
        pointObjectSchema,
        registrationMode,
        enumExtras: enumExtrasFromPointSchema(pointObjectSchema),
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
    return value.map((item) => (isImagePoint(item) ? item : item === null ? null : null));
}

/** Always returns an array (0–1 elements for single). Preserves null entries for registration. */
export function getPointsForImage(
    fieldValue: unknown,
    publicId: string,
    analysis: PointSchemaAnalysis,
): PointList {
    if (!analysis) return [];
    if (analysis.storageMode === "bare") {
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
    if (analysis.storageMode === "bare") {
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
