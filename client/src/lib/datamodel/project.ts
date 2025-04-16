import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";

export interface Project extends Item {
    id: number,
    name: string,
}

export const ProjectConstructor = new ItemConstructor<Project>(
    'ProjectID', {
    name: 'ProjectName'
});