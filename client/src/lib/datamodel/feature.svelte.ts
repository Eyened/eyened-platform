import { BaseItem } from "./itemList";

export interface ServerFeature {
    FeatureID: number,
    FeatureName: string,
}

export class Feature extends BaseItem {
    static endpoint = 'features';
    static mapping = {
        name: 'FeatureName',
    };

    id: number = 0;
    name: string = $state('');

    constructor(serverItem: ServerFeature) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerFeature) {
        this.id = serverItem.FeatureID;
        this.name = serverItem.FeatureName;
    }
}