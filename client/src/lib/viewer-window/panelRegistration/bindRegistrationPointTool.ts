import { formAnnotations, setFormAnnotationValue } from "$lib/data";
import {
    analyzePointSchema,
    getPointsForImage,
    setPointsForImage,
} from "$lib/forms/pointSchema";
import type { JSONSchema } from "$lib/forms/schemaType";
import type { PointMarkerStyle } from "$lib/config/clientDefaults";
import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";

const REGISTRATION_POINTS: JSONSchema = {
    type: "array",
    items: {
        oneOf: [
            {
                type: "object",
                properties: {
                    x: { type: "number" },
                    y: { type: "number" },
                    index: { type: ["number", "null"] },
                },
                required: ["x", "y"],
            },
            { type: "null" },
        ],
    },
};

function registrationAnalysis(schema: JSONSchema) {
    const withMarker = (value: JSONSchema): JSONSchema => ({
        ...value,
        type: "object",
        "x-eyened-widget": "keypoint",
    });
    const analyzed =
        analyzePointSchema(withMarker(schema)) ??
        analyzePointSchema(
            withMarker({ additionalProperties: REGISTRATION_POINTS }),
        );
    if (analyzed && analyzed.coordinateSpace === "enface2d") {
        return { ...analyzed, coordinateSpace: "oct" as const };
    }
    return analyzed;
}

export function bindRegistrationPointTool(args: {
    viewerContext: ViewerContext;
    annotationId: number;
    schema: JSONSchema;
    canEdit: boolean;
    pointMarker: { style: PointMarkerStyle; radius: number; color: string };
}): () => void {
    const analysis = registrationAnalysis(args.schema);
    if (!analysis) return () => {};
    const publicId = args.viewerContext.image.image_id;
    const annotationId = args.annotationId;
    const write = (
        points: ReturnType<typeof getPointsForImage>,
        persist: boolean,
    ) => {
        const existing = formAnnotations.get(annotationId);
        if (!existing) return;
        const next = setPointsForImage(
            existing.form_data,
            publicId,
            points,
            analysis,
        );
        formAnnotations.set(annotationId, { ...existing, form_data: next });
        if (persist) setFormAnnotationValue(annotationId, next);
    };
    const tool = new PointTool({
        canEdit: args.canEdit,
        label: "registration",
        pointStyle: args.pointMarker.style,
        radius: args.pointMarker.radius,
        color: args.pointMarker.color,
        cardinality: analysis.cardinality,
        sparse: analysis.sparse,
        coordinateSpace: analysis.coordinateSpace,
        onChange: (points) => write(points, false),
        onPersist: (points) => write(points, true),
    });
    const existing = formAnnotations.get(annotationId)?.form_data;
    tool.points = getPointsForImage(existing, publicId, analysis);
    const removeOverlay = args.viewerContext.addOverlay(tool);
    return () => {
        tool.destroy();
        removeOverlay();
    };
}
