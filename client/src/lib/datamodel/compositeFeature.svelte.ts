import type { Readable } from "svelte/store";
import type { Feature } from "./feature.svelte";
import { BaseItem } from "./baseItem";
import { data, registerConstructor } from "./model";

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
    primaryKey: [number, number, number] = [0, 0, 0];
    parentFeatureId: number = 0;
    childFeatureId: number = 0;
    featureIndex: number = $state(0);

    constructor(item: ServerCompositeFeature) {
        super();
        this.init(item);
    }

    init(serverItem: ServerCompositeFeature) {
        this.parentFeatureId = serverItem.ParentFeatureID;
        this.childFeatureId = serverItem.ChildFeatureID;
        this.featureIndex = serverItem.FeatureIndex;
        this.id = `${this.parentFeatureId}_${this.childFeatureId}_${this.featureIndex}`;
        this.primaryKey = [this.parentFeatureId, this.childFeatureId, this.featureIndex];
    }

    get parentFeature(): Feature {
        return data.features.get(this.parentFeatureId)!;
    }

    get childFeature(): Feature {
        return data.features.get(this.childFeatureId)!;
    }
}
registerConstructor('composite-features', CompositeFeature);

export function getCompositeFeatures(): Readable<Map<number, CompositeFeature[]>> {
    return data.compositeFeatures.filter(_ => true).groupBy(f => f.parentFeatureId);
}
