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

export function resolveFormEntityScope(
    schemaEntityType: FormSchemaGET["entity_type"] | null | undefined,
): FormEntityScope {
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
            return (annotation.study_id ?? null) === (ctx.studyId ?? null);
        case "Eye":
            return (annotation.laterality ?? null) === (ctx.laterality ?? null);
        case "StudyEye":
            return (
                (annotation.study_id ?? null) === (ctx.studyId ?? null) &&
                (annotation.laterality ?? null) === (ctx.laterality ?? null)
            );
        case "ImageInstance":
            return (annotation.image_id ?? null) === (ctx.imageId ?? null);
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
