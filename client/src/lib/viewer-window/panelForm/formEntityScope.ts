import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../../types/openapi_types";

export type FormEntityScope = NonNullable<FormSchemaGET["entity_type"]>;

export type FormAnnotationContext = {
    patientId: number;
    studyId?: number;
    imageId?: string;
    laterality?: FormAnnotationGET["laterality"];
};

export type TaskFormScopeConfig = {
    form_entity_scope?: FormEntityScope;
    /** @deprecated Use `form_entity_scope: "ImageInstance"` instead. */
    form_image_scope?: boolean;
};

export function resolveFormEntityScope(
    taskConfig: TaskFormScopeConfig | undefined,
    schemaEntityType: FormSchemaGET["entity_type"],
): FormEntityScope {
    if (taskConfig?.form_entity_scope) {
        return taskConfig.form_entity_scope;
    }
    if (taskConfig?.form_image_scope === true) {
        return "ImageInstance";
    }
    return schemaEntityType ?? "ImageInstance";
}

export function matchesFormEntityScope(
    annotation: FormAnnotationGET,
    scope: FormEntityScope,
    ctx: FormAnnotationContext,
): boolean {
    if (annotation.patient_id !== ctx.patientId) {
        return false;
    }

    switch (scope) {
        case "Patient":
            return true;
        case "Study":
            return annotation.study_id === ctx.studyId;
        case "Eye":
            return annotation.laterality === ctx.laterality;
        case "StudyEye":
            return (
                annotation.study_id === ctx.studyId &&
                annotation.laterality === ctx.laterality
            );
        case "ImageInstance":
            return annotation.image_id === ctx.imageId;
        default:
            return false;
    }
}

export function buildFormAnnotationCreatePayload(input: {
    formSchemaId: number;
    scope: FormEntityScope;
    ctx: FormAnnotationContext;
    subTaskId?: number;
}): {
    form_schema_id: number;
    patient_id: number;
    study_id?: number;
    image_id?: string;
    laterality?: FormAnnotationGET["laterality"];
    sub_task_id?: number;
    form_data: Record<string, never>;
} {
    const base = {
        form_schema_id: input.formSchemaId,
        patient_id: input.ctx.patientId,
        sub_task_id: input.subTaskId,
        form_data: {} as Record<string, never>,
    };

    switch (input.scope) {
        case "Patient":
            return base;
        case "Study":
            return { ...base, study_id: input.ctx.studyId };
        case "Eye":
            return { ...base, laterality: input.ctx.laterality };
        case "StudyEye":
            return {
                ...base,
                study_id: input.ctx.studyId,
                laterality: input.ctx.laterality,
            };
        case "ImageInstance":
            return {
                ...base,
                study_id: input.ctx.studyId,
                image_id: input.ctx.imageId,
                laterality: input.ctx.laterality,
            };
        default:
            return base;
    }
}
