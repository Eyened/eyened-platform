import { BaseItem } from "./itemList";

export type DataRepresentation = 'BINARY' | 'RG_MASK' | 'FLOAT' | 'MULTI_LABEL' | 'MULTI_CLASS';

export interface ServerAnnotationType {
    AnnotationTypeID: number;
    AnnotationTypeName: string;
    DataRepresentation: DataRepresentation;
}

export class AnnotationType extends BaseItem {
    static mapping = {
        'AnnotationTypeName': 'name',
        'DataRepresentation': 'dataRepresentation',
    };
    static endpoint = 'annotationTypes';

    id!: number;
    name!: string;
    dataRepresentation!: DataRepresentation;

    constructor(serverItem: ServerAnnotationType) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerAnnotationType) {
        this.id = serverItem.AnnotationTypeID;
        this.name = serverItem.AnnotationTypeName;
        this.dataRepresentation = serverItem.DataRepresentation;
    }
}

export interface ServerAnnotationTypeFeature {
    AnnotationTypeID: number;
    FeatureID: number;
    FeatureIndex: number;
}

export class AnnotationTypeFeature extends BaseItem {
    static mapping = {
        'AnnotationTypeID': 'annotationTypeId',
        'FeatureID': 'featureId',
        'FeatureIndex': 'featureIndex',
    };
    static endpoint = 'annotationTypeFeatures';

    id!: string;
    annotationTypeId!: number;
    featureId!: number;
    featureIndex!: number;

    constructor(serverItem: ServerAnnotationTypeFeature) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerAnnotationTypeFeature) {
        this.id = `${serverItem.AnnotationTypeID}_${serverItem.FeatureID}_${serverItem.FeatureIndex}`;
        this.annotationTypeId = serverItem.AnnotationTypeID;
        this.featureId = serverItem.FeatureID;
        this.featureIndex = serverItem.FeatureIndex;
    }
}