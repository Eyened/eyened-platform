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
        AnnotationID: 'annotationId',
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
    valueFloat?: number = $state(undefined);
    valueInt?: number = $state(undefined);
    file!: DataEndpoint<any>;

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
        this.file = new DataEndpoint<any>(`${AnnotationData.endpoint}/${this.id}/file`);
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