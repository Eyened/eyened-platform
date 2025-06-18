import type { Annotation } from "./annotation.svelte";
import { DataEndpoint } from "./api.svelte";
import { BaseItem } from "./itemList";
import { data } from "./model";

export type AnnotationPlane = 'PRIMARY' | 'SECONDARY' | 'TERTIARY' | 'VOLUME';

export interface ServerAnnotationData {
    AnnotationDataID: number;
    AnnotationID: number;
    ScanNr: number;
    AnnotationPlane: AnnotationPlane;
    DateModified: Date;
    DatasetIdentifier: string;
    ValueFloat: number;
    ValueInt: number;
}


export class AnnotationData extends BaseItem {
    static endpoint = 'annotation-data';
    static mapping = {
        ScanNr: 'scanNr',
        AnnotationPlane: 'annotationPlane',
        DateModified: 'modified',
        DatasetIdentifier: 'datasetIdentifier',
        ValueFloat: 'valueFloat',
        ValueInt: 'valueInt',
    };

    id!: string;
    annotationId!: number;
    scanNr!: number;
    annotationPlane!: AnnotationPlane;
    modified!: Date;
    datasetIdentifier!: string;
    valueFloat?: number;
    valueInt?: number;
    value!: DataEndpoint<any>;

    constructor(serverItem: ServerAnnotationData) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerAnnotationData) {
        this.id = `${serverItem.AnnotationID}_${serverItem.ScanNr}`;
        this.annotationId = serverItem.AnnotationID;
        this.scanNr = serverItem.ScanNr;
        this.annotationPlane = serverItem.AnnotationPlane;
        this.modified = serverItem.DateModified;
        this.datasetIdentifier = serverItem.DatasetIdentifier;
        this.valueFloat = serverItem.ValueFloat;
        this.valueInt = serverItem.ValueInt;
        this.value = new DataEndpoint<any>(`${AnnotationData.endpoint}/${this.id}/value`);
    }

    static createFrom(annotation: Annotation, scanNr: number, annotationPlane: string) {
        AnnotationData.create({
            annotationId: annotation.id,
            scanNr,
            annotationPlane
        });
    }

    get annotation(): Annotation {
        return data.annotations.get(this.annotationId)!;
    }
}

// export interface AnnotationData extends Item {
//     id: string,
//     annotation: Annotation,
//     annotationType: AnnotationType,
//     feature: Feature,
//     scanNr: number,
//     annotationPlane: AnnotationPlane,    
//     modified?: Date,
//     filename: string,
//     value: ServerProperty<any>,

//     parameters: ServerProperty<{
//         valuefloat?: number,
//         valueint?: number
//     }>
// }
// interface AnnotationDataParameters {
//     valuefloat?: number,
//     valueint?: number
// }

// const parameters: ItemMapping<any> = {
//     toValue: (params: any) => {
//         const endpoint = `annotation-data/${params.AnnotationID}_${params.ScanNr}/parameters`;
//         const initialValue = {
//             valuefloat: params.ValueFloat,
//             valueint: params.ValueInt
//         };
//         return new WriteOnlyServerProperty<AnnotationDataParameters>({ endpoint, initialValue });
//     },
//     toParam: (params: any, value: WriteOnlyServerProperty<AnnotationDataParameters>) => {
//         params.valueFloat = value.value?.valuefloat;
//         params.valueInt = value.value?.valueint;
//     }
// }

// const value = ServerPropertyMapping(null, params => `annotation-data/${params.AnnotationID}_${params.ScanNr}/file`, false);
// export const AnnotationDataConstructor = new ItemConstructor<AnnotationData>(
//     (params: any) => `${params.AnnotationID}_${params.ScanNr}`, {
//     annotation: FKMapping('AnnotationID', 'annotations'),
//     annotationType: PropertyChain(['annotation', 'annotationType']),
//     feature: PropertyChain(['annotation', 'feature']),
//     scanNr: 'ScanNr',
//     annotationPlane: 'AnnotationPlane',
//     modified: 'DateModified',
//     filename: 'DatasetIdentifier',
//     value,
//     parameters
// });
