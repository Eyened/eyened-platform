import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";

export interface Scan extends Item {
    mode: string
}

export const ScanConstructor = new ItemConstructor<Scan>(
    'ScanID', {
    mode: 'ScanMode',
});