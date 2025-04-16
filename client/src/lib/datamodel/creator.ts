import type { Annotation } from "./annotation";
import { DerivedProperty, ItemConstructor } from "./itemContructor";
import type { FilterList, Item } from "./itemList";
import type { DataModel } from "./model";

export interface Creator extends Item {
    id: number;
    name: string;
    msn?: string;
    isHuman: boolean;
    description?: string;
    version?: string;
    role?: any;
    annotations: FilterList<Annotation>;
}

export const CreatorConstructor = new ItemConstructor<Creator>(
    'CreatorID', {
    name: 'CreatorName',
    msn: 'MSN',
    isHuman: 'IsHuman',
    description: 'Description',
    version: 'Version',
    role: 'Role',
    annotations: new DerivedProperty((self: Creator, data: DataModel) => data.annotations.filter(annotation => annotation.creator == self))
});