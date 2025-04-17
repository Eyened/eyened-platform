import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";

export interface Feature extends Item {
    id: number,
    name: string,
}
export const FeatureConstructor = new ItemConstructor<Feature>(
    'FeatureID', {
    name: 'FeatureName'
});