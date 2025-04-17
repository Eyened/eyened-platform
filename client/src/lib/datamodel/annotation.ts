import type { AnnotationTypeInterpretation } from "$lib/types";
import type { AnnotationData } from "./annotationData";
import type { AnnotationType } from "./annotationType";
import type { Creator } from "./creator";
import type { Feature } from "./feature";
import type { Instance } from "./instance";
import { DerivedProperty, ItemConstructor, PropertyChain } from "./itemContructor";
import type { FilterList, Item } from "./itemList";
import { DateMapping, FKMapping } from "./mapping";
import { data, type DataModel } from "./model";
import type { Patient } from "./patient";
import type { Series } from "./series";
import type { Study } from "./study";

export interface Annotation extends Item {
    id: number,
    patient?: Patient,
    study?: Study,
    series?: Series,
    instance?: Instance,
    annotationReference?: Annotation,
    creator: Creator,
    feature: Feature,
    annotationType: AnnotationType,
    interpretation: AnnotationTypeInterpretation,
    created?: Date,
    inactive?: boolean,
    annotationDatas: FilterList<AnnotationData>
}

export const AnnotationConstructor = new ItemConstructor<Annotation>(
    'AnnotationID', {
    patient: FKMapping('PatientID', 'patients'),
    study: FKMapping('StudyID', 'studies'),
    series: FKMapping('SeriesID', 'series'),
    instance: FKMapping('ImageInstanceID', 'instances'),
    annotationReference: FKMapping('AnnotationReferenceID', 'annotations'),
    creator: FKMapping('CreatorID', 'creators'),
    feature: FKMapping('FeatureID', 'features'),
    annotationType: FKMapping('AnnotationTypeID', 'annotationTypes'),
    interpretation: PropertyChain(['annotationType', 'interpretation']),
    created: DateMapping('DateInserted'),
    inactive: 'Inactive',

    annotationDatas: new DerivedProperty((self: Annotation, data: DataModel) => {
        return data.annotationDatas.filter(annotationData => annotationData.annotation == self).sort((a, b) => a.scanNr - b.scanNr);
    })

});

export async function createAnnotation(instance: Instance, feature: Feature, creator: Creator, annotationType: AnnotationType): Promise<Annotation> {
    const { annotations } = data;
    const annotationItem = {
        instance,
        series: instance.series,
        study: instance.study,
        patient: instance.patient,
        creator,
        feature,
        annotationType
    };
    return annotations.create(annotationItem);
}
