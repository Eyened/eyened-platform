import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../../types/openapi_types";
import {
    type FormAnnotationContext,
    matchesFormEntityScope,
    resolveFormEntityScope,
    type TaskFormScopeConfig,
} from "./formEntityScope";

export type FindFormAnnotationParams = {
    annotations: FormAnnotationGET[];
    schemaId: number;
    userId: number;
    ctx: FormAnnotationContext;
    subTaskId?: number;
    taskConfig?: TaskFormScopeConfig;
    schemaEntityType: FormSchemaGET["entity_type"];
};

export function findFormAnnotation(
    params: FindFormAnnotationParams,
): FormAnnotationGET | undefined {
    const scope = resolveFormEntityScope(
        params.taskConfig,
        params.schemaEntityType,
    );

    const matches = params.annotations.filter((annotation) => {
        if (annotation.form_schema_id !== params.schemaId) return false;
        if (annotation.creator?.id !== params.userId) return false;
        if (
            params.subTaskId !== undefined &&
            annotation.sub_task_id !== params.subTaskId
        ) {
            return false;
        }
        return matchesFormEntityScope(annotation, scope, params.ctx);
    });

    if (!matches.length) return undefined;
    return matches.reduce((best, current) =>
        current.id > best.id ? current : best,
    );
}
