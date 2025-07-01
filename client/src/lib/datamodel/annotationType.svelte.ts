import type { Feature } from "./feature.svelte";
import { BaseItem, BaseLinkingItem, FilterList } from "./itemList";
import { data } from "./model";

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
    static endpoint = 'annotation-types';

    id!: number;
    name: string = $state("");
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

    get baseFeature(): Feature | undefined {
        return data.annotationTypeFeatures
            .filter(f => f.annotationTypeId == this.id)
            .filter(f => f.featureIndex == -1)
            .map(f => f.feature)
            .first();
    }

    get annotatedFeatures(): FilterList<AnnotationTypeFeature> {
        return data.annotationTypeFeatures
            .filter(f => f.annotationTypeId == this.id)
            .filter((f) => f.featureIndex >= 0);
    }
}

export interface ServerAnnotationTypeFeature {
    AnnotationTypeID: number;
    FeatureID: number;
    FeatureIndex: number;
}

export class AnnotationTypeFeature extends BaseLinkingItem {
    static endpoint = 'annotation-type-features';
    static parentResource = 'annotation-types';
    static childResource = 'features';
    static parentIdField = 'annotationTypeId';
    static childIdField = 'featureId';
    static mapping = {
        'AnnotationTypeID': 'annotationTypeId',
        'FeatureID': 'featureId',
        'FeatureIndex': 'featureIndex'
    };

    id!: string;
    featureIndex!: number;
    annotationTypeId!: number;
    featureId!: number;

    constructor(item: ServerAnnotationTypeFeature) {
        super(item.AnnotationTypeID, item.FeatureID);
        this.init(item);
    }

    init(serverItem: ServerAnnotationTypeFeature) {
        this.id = `${serverItem.AnnotationTypeID}_${serverItem.FeatureID}_${serverItem.FeatureIndex}`;
        this.annotationTypeId = serverItem.AnnotationTypeID;
        this.featureId = serverItem.FeatureID;
        this.featureIndex = serverItem.FeatureIndex;
    }

    get feature(): Feature {
        return data.features.get(this.featureId)!;
    }

    get annotationType(): AnnotationType {
        return data.annotationTypes.get(this.annotationTypeId)!;
    }


}