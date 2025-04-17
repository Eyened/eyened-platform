import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";

export interface TaskState extends Item {
    id: number;
    name: string;
}

export const TaskStateConstructor = new ItemConstructor<TaskState>(
    'TaskStateID', {
    name: 'TaskStateName',
});