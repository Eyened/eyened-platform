import { DerivedProperty, ItemConstructor } from "./itemContructor";
import type { FilterList, Item } from "./itemList";
import { FKMapping } from "./mapping";
import type { TaskDefinition } from "./taskDefinition";
import type { DataModel } from "./model";
import type { SubTask } from "./subTask";

export interface Task extends Item {
    id: number,
    name: string,
    definition: TaskDefinition,
    state: string,
    subTasks: FilterList<SubTask>
}

export const TaskConstructor = new ItemConstructor<Task>('TaskID', {
    name: 'TaskName',
    definition: FKMapping('TaskDefinitionID', 'taskDefinitions'),
    state: 'TaskState',
    subTasks: new DerivedProperty((self: Task, data: DataModel) => data.subTasks.filter(subtask => subtask.task === self))
});