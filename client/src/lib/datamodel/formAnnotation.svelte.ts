import type { Creator } from "./creator.svelte";
import type { FormSchema } from "./formSchema.svelte";
import type { Instance } from "./instance.svelte";  
import { BaseItem } from "./baseItem";
import { data, registerConstructor } from "./model";
import type { Patient } from "./patient";
import type { Study } from "./study";
import type { SubTask } from "./subTask.svelte";
import { api } from '../utils/api';

export interface ServerFormAnnotation {
    FormAnnotationID: number,
    FormSchemaID: number,
    PatientID: number,
    StudyID: number,
    ImageInstanceID: number,
    CreatorID: number,
    SubTaskID: number,
    DateInserted: Date,
    DateModified: Date,
    FormAnnotationReferenceID: number,
    FormData: any,
}

export class FormAnnotation extends BaseItem {
    static endpoint = 'form-annotations';
    static mapping = {
        'FormSchemaID': 'formSchemaId',
        'PatientID': 'patientId',
        'StudyID': 'studyId',
        'ImageInstanceID': 'instanceId',
        'CreatorID': 'creatorId',
        'SubTaskID': 'subTaskId',
        'DateInserted': 'created',
        'DateModified': 'modified',
        'FormAnnotationReferenceID': 'referenceId',
        'FormData': 'value',
    };
    id!: number;
    formSchemaId!: number;
    patientId!: number;
    studyId!: number;
    instanceId!: number;
    creatorId!: number;
    subTaskId!: number;
    created!: Date;
    modified!: Date;
    referenceId!: number;
    value: any = $state(undefined);


    constructor(serverItem: ServerFormAnnotation) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerFormAnnotation) {
        this.id = serverItem.FormAnnotationID;
        this.formSchemaId = serverItem.FormSchemaID;
        this.patientId = serverItem.PatientID;
        this.studyId = serverItem.StudyID;
        this.instanceId = serverItem.ImageInstanceID;
        this.creatorId = serverItem.CreatorID;
        this.subTaskId = serverItem.SubTaskID;
        this.created = new Date(serverItem.DateInserted);
        this.modified = new Date(serverItem.DateModified);
        this.referenceId = serverItem.FormAnnotationReferenceID;
        this.value = serverItem.FormData;
    }

    async load() {
        const response = await api.get(`${FormAnnotation.endpoint}/${this.id}/form-data`);
        this.value = await response.json();
    }

    static async createFrom(creator: Creator, instance: Instance, formSchema: FormSchema, subTask?: SubTask, reference?: FormAnnotation) {
        return FormAnnotation.create({
            creatorId: creator.id,
            instanceId: instance.id,
            patientId: instance.patient.id,
            studyId: instance.study.id,
            formSchemaId: formSchema.id,
            subTaskId: subTask?.id,
            referenceId: reference?.id,
            value: reference?.value,
        });
    }

    public get formSchema(): FormSchema {
        return data.formSchemas.get(this.formSchemaId)!;
    }

    public get patient(): Patient {
        return data.patients.get(this.patientId)!;
    }

    public get study(): Study {
        return data.studies.get(this.studyId)!;
    }

    public get instance(): Instance {
        return data.instances.get(this.instanceId)!;
    }

    public get creator(): Creator {
        return data.creators.get(this.creatorId)!;
    }

    public get reference(): FormAnnotation | undefined {
        if (!this.referenceId) return undefined;
        return data.formAnnotations.get(this.referenceId);
    }
}   
registerConstructor('form-annotations', FormAnnotation);