import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../../types/openapi_types";

export type FindFormAnnotationParams = {
    annotations: FormAnnotationGET[];
    schemaId: number;
    userId: number;
    patientId: number;
    studyId?: number;
    imageId?: number;
    laterality?: FormAnnotationGET["laterality"];
    subTaskId?: number;
    formImageScope: boolean;
    entityType: FormSchemaGET["entity_type"];
};

function matchesEntityContext(
    annotation: FormAnnotationGET,
    params: FindFormAnnotationParams,
): boolean {
    if (params.formImageScope) {
        return annotation.image_id === params.imageId;
    }
    if (params.entityType === "StudyEye") {
        return (
            annotation.study_id === params.studyId &&
            annotation.laterality === params.laterality
        );
    }
    return annotation.image_id === params.imageId;
}

export function findFormAnnotation(
    params: FindFormAnnotationParams,
): FormAnnotationGET | undefined {
    const matches = params.annotations.filter((annotation) => {
        if (annotation.form_schema_id !== params.schemaId) return false;
        if (annotation.creator?.id !== params.userId) return false;
        if (annotation.patient_id !== params.patientId) return false;
        if (
            params.subTaskId !== undefined &&
            annotation.sub_task_id !== params.subTaskId
        ) {
            return false;
        }
        return matchesEntityContext(annotation, params);
    });

    if (!matches.length) return undefined;
    return matches.reduce((best, current) =>
        current.id > best.id ? current : best,
    );
}
