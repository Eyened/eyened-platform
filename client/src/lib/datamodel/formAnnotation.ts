import type { Creator } from "./creator";
import type { FormSchema } from "./formSchema";
import type { Instance } from "./instance";
import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";
import { DateMapping, FKMapping, ServerPropertyMapping } from "./mapping";
import type { Patient } from "./patient";
import type { ServerProperty } from "./serverProperty.svelte";
import type { Study } from "./study";
import type { SubTask } from "./subTask";

export interface FormAnnotation extends Item {
    id: number,
    formSchema: FormSchema,
    patient: Patient,
    study?: Study
    instance?: Instance
    creator: Creator,
    subTask?: SubTask,
    created?: Date,
    modified?: Date,
    reference: FormAnnotation | null,
    value: ServerProperty<any>
}

export const FormAnnotationConstructor = new ItemConstructor<FormAnnotation>(
    'FormAnnotationID',
    {
        formSchema: FKMapping('FormSchemaID', 'formSchemas'),
        patient: FKMapping('PatientID', 'patients'),
        study: FKMapping('StudyID', 'studies'),
        instance: FKMapping('ImageInstanceID', 'instances'),
        creator: FKMapping('CreatorID', 'creators'),
        subTask: FKMapping('SubTaskID', 'subTasks'),
        created: DateMapping('DateInserted'),
        modified: DateMapping('DateModified'),
        reference: FKMapping('FormAnnotationReferenceID', 'formAnnotations'),
        value: ServerPropertyMapping('FormData', params => `formAnnotations/${params.FormAnnotationID}/value`, params => 'application/json', true)
    });