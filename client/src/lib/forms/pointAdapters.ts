import {
    getPointsForImage,
    setPointsForImage,
    type ImagePoint,
    type PointList,
    type PointSchemaAnalysis,
} from "./pointSchema";

export type PointAdapter = {
    analysis: PointSchemaAnalysis;
    getPublicId: () => string;
    getPoints: () => PointList;
    setPoints: (points: PointList) => void;
    slotLabels?: readonly string[];
};

function isImagePoint(value: unknown): value is ImagePoint {
    return (
        typeof value === "object" &&
        value !== null &&
        typeof (value as ImagePoint).x === "number" &&
        typeof (value as ImagePoint).y === "number"
    );
}

export function createFieldAdapter(args: {
    analysis: PointSchemaAnalysis;
    getPublicId: () => string;
    getFieldValue: () => unknown;
    setFieldValue: (next: unknown) => void;
}): PointAdapter {
    return {
        analysis: args.analysis,
        getPublicId: args.getPublicId,
        getPoints: () =>
            getPointsForImage(
                args.getFieldValue(),
                args.getPublicId(),
                args.analysis,
            ),
        setPoints: (points) => {
            args.setFieldValue(
                setPointsForImage(
                    args.getFieldValue(),
                    args.getPublicId(),
                    points,
                    args.analysis,
                ),
            );
        },
    };
}

const MULTI_FIELD_POINT_SCHEMA = {
    type: "object",
    properties: {
        x: { type: "number" },
        y: { type: "number" },
    },
    required: ["x", "y"],
} as const;

/**
 * ETDRS-style: named sibling keypoint fields ↔ one sparse list for PointTool.
 * `slotLabels` default to `slots` (use schema titles from the panel when available).
 */
export function createMultiFieldAdapter(args: {
    slots: readonly string[];
    slotLabels?: readonly string[];
    getPublicId: () => string;
    getFormData: () => Record<string, unknown>;
    setFormData: (next: Record<string, unknown>) => void;
}): PointAdapter {
    const analysis: PointSchemaAnalysis = {
        cardinality: "list",
        addressing: "bare",
        sparse: true,
        pointObjectSchema: { ...MULTI_FIELD_POINT_SCHEMA },
        enumExtras: [],
        coordinateSpace: "enface2d",
    };
    return {
        analysis,
        getPublicId: args.getPublicId,
        slotLabels: args.slotLabels ?? args.slots,
        getPoints: () => {
            const data = args.getFormData();
            return args.slots.map((slot) => {
                const v = data[slot];
                return isImagePoint(v) ? v : null;
            });
        },
        setPoints: (points) => {
            const data = { ...args.getFormData() };
            for (let i = 0; i < args.slots.length; i++) {
                const slot = args.slots[i]!;
                const pt = points[i] ?? null;
                if (pt == null) delete data[slot];
                else data[slot] = pt;
            }
            args.setFormData(data);
        },
    };
}
