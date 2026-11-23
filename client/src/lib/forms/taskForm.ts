import { CLIENT_DEFAULTS, mergeClientConfig } from "$lib/config/clientDefaults";
import type { FormAnnotationGET } from "../../types/openapi_types";

/** The schema name the task grades with, from its config. */
export function taskFormName(config: unknown): string | undefined {
    return mergeClientConfig(CLIENT_DEFAULTS, config).form_schema_name;
}

/** A copy with the same answers; in a task it joins this set. */
export function copyPayload(form: FormAnnotationGET, subTaskId?: number) {
    return {
        form_schema_id: form.form_schema_id,
        patient_id: form.patient_id,
        study_id: form.study_id ?? undefined,
        image_id: form.image_id ?? undefined,
        laterality: form.laterality ?? undefined,
        sub_task_id: subTaskId ?? form.sub_task_id ?? undefined,
        form_data: form.form_data,
        form_annotation_reference_id: form.id,
    };
}
