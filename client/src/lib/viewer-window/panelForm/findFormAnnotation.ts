import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../../types/openapi_types";
import {
    type FormAnnotationContext,
    matchesFormEntityScope,
    resolveFormEntityScope,
} from "./formEntityScope";

export type FindFormAnnotationParams = {
    annotations: FormAnnotationGET[];
    schemaId: number;
    userId: number;
    ctx: FormAnnotationContext;
    subTaskId?: number;
    schemaEntityType: FormSchemaGET["entity_type"];
};

export function findFormAnnotation(
    params: FindFormAnnotationParams,
): FormAnnotationGET | undefined {
    const matches = params.annotations.filter((annotation) => {
        if (annotation.form_schema_id !== params.schemaId) return false;
        if (annotation.creator?.id !== params.userId) return false;

        if (params.subTaskId !== undefined) {
            return annotation.sub_task_id === params.subTaskId;
        }

        const scope = resolveFormEntityScope(params.schemaEntityType);
        return matchesFormEntityScope(annotation, scope, params.ctx);
    });

    if (!matches.length) return undefined;
    return matches.reduce((best, current) =>
        current.id > best.id ? current : best,
    );
}
