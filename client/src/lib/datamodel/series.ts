import type { Instance } from "./instance";
import { DerivedProperty, ItemConstructor } from "./itemContructor";
import type { FilterList, Item } from "./itemList";
import { FKMapping } from "./mapping";
import type { DataModel } from "./model";
import type { Study } from "./study";

export interface Series extends Item {
    id: number,
    study: Study,
    instances: FilterList<Instance>
}
export const SeriesConstructor = new ItemConstructor<Series>('SeriesID', {
    study: FKMapping('StudyID', 'studies'),
    instances: new DerivedProperty((self: Series, data: DataModel) => data.instances.filter(instance => instance.series == self))
});