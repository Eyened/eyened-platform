import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";
import { FKMapping } from "./mapping";
import type { SubTask } from "./subTask";

export interface SubTaskImageLink extends Item {
    instanceid: number;
    subTask: SubTask;
}

export const SubTaskImageLinkConstructor = new ItemConstructor<SubTaskImageLink>(
    'SubTaskImageLinkID', {
    instanceid: 'ImageInstanceID', // FK not resolved because they are not automatically loaded
    subTask: FKMapping('SubTaskID', 'subTasks')
});
