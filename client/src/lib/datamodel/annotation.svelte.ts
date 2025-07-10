import type { AnnotationData } from "./annotationData.svelte";
import type { AnnotationType } from "./annotationType.svelte";
import { DataEndpoint } from "./api.svelte";
import type { Creator } from "./creator.svelte";
import type { Feature } from "./feature.svelte";
import type { Instance } from "./instance.svelte";
import { BaseItem, type FilterList } from "./itemList";
import { data } from "./model";
import type { Patient } from "./patient";
import type { Study } from "./study";

export interface ServerAnnotation {
    AnnotationID: number;
    PatientID: number;
    StudyID: number;
    SeriesID: number;
    ImageInstanceID: number;
    AnnotationReferenceID: number;
    CreatorID: number;
    FeatureID: number;
    AnnotationTypeID: number;
    DateInserted: Date;
    Inactive: boolean;
}

export class Annotation extends BaseItem {

    static mapping = {
        PatientID: 'patientId',
        StudyID: 'studyId',
        SeriesID: 'seriesId',
        ImageInstanceID: 'instanceId',
        AnnotationReferenceID: 'annotationReferenceId',
        CreatorID: 'creatorId',
        FeatureID: 'featureId',
        AnnotationTypeID: 'annotationTypeId',
        DateInserted: 'created',
    };
    static endpoint = 'annotations';

    id!: number;
    patientId?: number;
    studyId?: number;
    seriesId?: number;
    instanceId?: number;
    annotationReferenceId?: number = $state(undefined);
    creatorId!: number;
    featureId!: number;
    annotationTypeId!: number;
    created!: Date;
    file!: DataEndpoint<any>;

    constructor(serverItem: ServerAnnotation) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerAnnotation) {
        this.id = serverItem.AnnotationID;
        this.patientId = serverItem.PatientID;
        this.studyId = serverItem.StudyID;
        this.seriesId = serverItem.SeriesID;
        this.instanceId = serverItem.ImageInstanceID;
        this.annotationReferenceId = serverItem.AnnotationReferenceID;
        this.creatorId = serverItem.CreatorID;
        this.featureId = serverItem.FeatureID;
        this.annotationTypeId = serverItem.AnnotationTypeID;
        this.created = serverItem.DateInserted;
        this.file = new DataEndpoint<any>(`${Annotation.endpoint}/${this.id}/file`);
        
    }

    static async createFrom(instance: Instance, feature: Feature, creator: Creator, annotationType: AnnotationType) {
        return Annotation.create({
            instanceId: instance.id,
            seriesId: instance.seriesId,
            studyId: instance.study.id,
            patientId: instance.patient.id,
            featureId: feature.id,
            creatorId: creator.id,
            annotationTypeId: annotationType.id,
        });
    }

    get creator(): Creator {
        return data.creators.get(this.creatorId)!;
    }
    get annotationType(): AnnotationType {
        return data.annotationTypes.get(this.annotationTypeId)!;
    }
    get feature(): Feature {
        return data.features.get(this.featureId)!;
    }
    get instance(): Instance {
        return data.instances.get(this.instanceId!)!;
    }
    get study(): Study {
        return data.studies.get(this.studyId!)!;
    }
    get patient(): Patient {
        return data.patients.get(this.patientId!)!;
    }
    get annotationData(): FilterList<AnnotationData> {
        return data.annotationData.filter(annotationData => annotationData.annotationId == this.id);
    }
    get annotationReference(): Annotation | undefined {
        if (!this.annotationReferenceId) return undefined;
        return data.annotations.get(this.annotationReferenceId);
    }
}