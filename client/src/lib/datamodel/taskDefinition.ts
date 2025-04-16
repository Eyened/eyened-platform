import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";

export interface TaskDefinition extends Item {
    id: number,
    name: string,
}

export const TaskDefinitionConstructor = new ItemConstructor<TaskDefinition>(
    'TaskDefinitionID', {
    name: 'TaskDefinitionName'
});