import type { Readable } from "svelte/store";
import type { Feature } from "./feature.svelte";
import { BaseItem } from "./itemList";
import { data } from "./model";

export interface ServerCompositeFeature {
    ParentFeatureID: number,
    ChildFeatureID: number,
    FeatureIndex: number,
}

export class CompositeFeature extends BaseItem {

    static endpoint = 'composite-features';
    static mapping = {
        'ParentFeatureID': 'parentFeatureId',
        'ChildFeatureID': 'childFeatureId',
        'FeatureIndex': 'featureIndex',
    };

    id!: string;
    parentFeatureId: number = 0;
    childFeatureId: number = 0;
    featureIndex: number = 0;

    constructor(item: ServerCompositeFeature) {
        super();
        this.init(item);
    }

    init(serverItem: ServerCompositeFeature) {
        this.parentFeatureId = serverItem.ParentFeatureID;
        this.childFeatureId = serverItem.ChildFeatureID;
        this.featureIndex = serverItem.FeatureIndex;
        this.id = `${this.parentFeatureId}_${this.childFeatureId}_${this.featureIndex}`;
    }

    get parentFeature(): Feature {
        return data.features.get(this.parentFeatureId)!;
    }

    get childFeature(): Feature {
        return data.features.get(this.childFeatureId)!;
    }
}

export function getCompositeFeatures(): Readable<Map<number, CompositeFeature[]>> {
    return data.compositeFeatures.filter(_ => true).groupBy(f => f.parentFeatureId);
}
