import type { Annotation } from "./annotation";
import type { AnnotationType } from "./annotationType";
import type { Creator } from "./creator";
import type { Feature } from "./feature";
import type { Instance } from "./instance";
import { ItemConstructor, PropertyChain } from "./itemContructor";
import type { Item } from "./itemList";
import { FKMapping, ServerPropertyMapping, type ItemMapping } from "./mapping";
import { data } from "./model";
import { ServerProperty, WriteOnlyServerProperty } from "./serverProperty.svelte";

export interface AnnotationData extends Item {
    id: string,
    annotation: Annotation,
    annotationType: AnnotationType,
    feature: Feature,
    scanNr: number,
    mediaType: string,
    modified?: Date,
    value: ServerProperty<any>,
    parameters: ServerProperty<{
        valuefloat?: number,
        valueint?: number
    }>
}
interface AnnotationDataParameters {
    valuefloat?: number,
    valueint?: number
}

const parameters: ItemMapping<any> = {
    toValue: (params: any) => {
        const endpoint = `annotationDatas/${params.AnnotationID}_${params.ScanNr}/parameters`;
        const mediaType = 'application/json';
        const initialValue = {
            valuefloat: params.ValueFloat,
            valueint: params.ValueInt
        };
        return new WriteOnlyServerProperty<AnnotationDataParameters>({ endpoint, mediaType, initialValue });
    },
    toParam: (params: any, value: WriteOnlyServerProperty<AnnotationDataParameters>) => {
        params.valueFloat = value.value?.valuefloat;
        params.valueInt = value.value?.valueint;
    }
}

const value = ServerPropertyMapping(null, params => `annotationDatas/${params.AnnotationID}_${params.ScanNr}/value`, params => params.MediaType, false);
export const AnnotationDataConstructor = new ItemConstructor<AnnotationData>(
    (params: any) => `${params.AnnotationID}_${params.ScanNr}`, {
    annotation: FKMapping('AnnotationID', 'annotations'),
    annotationType: PropertyChain(['annotation', 'annotationType']),
    feature: PropertyChain(['annotation', 'feature']),
    scanNr: 'ScanNr',
    mediaType: 'MediaType',
    modified: 'DateModified',
    value,
    parameters
});

export async function createAnnotationData(annotation: Annotation, scanNr: number, mediaType: string): Promise<AnnotationData> {
    const annotationDataItem = {
        annotation,
        scanNr,
        mediaType
    };
    return data.annotationDatas.create(annotationDataItem);
}


export async function createJSONAnnotation(
    instance: Instance,
    annotationType: AnnotationType,
    creator: Creator,
    feature: Feature,
    value: any): Promise<AnnotationData> {
    const { annotations, annotationDatas } = data;
    const annotationItem = {
        instance,
        series: instance.series,
        study: instance.study,
        patient: instance.patient,
        annotationType,
        creator,
        feature
    };
    const annotation = await annotations.create(annotationItem);

    const annotationDataItem = {
        annotation,
        scanNr: 0,
        mediaType: 'application/json'
    };
    const annotationData = await annotationDatas.create(annotationDataItem);

    await annotationData.value?.setValue(value);

    return annotationData;
}