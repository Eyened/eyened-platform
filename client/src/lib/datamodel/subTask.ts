import { derived, type Readable } from "svelte/store";
import type { Creator } from "./creator";
import { DerivedProperty, ItemConstructor } from "./itemContructor";
import type { FilterList, Item } from "./itemList";
import { FKMapping } from "./mapping";
import type { DataModel } from "./model";
import { WriteOnlyServerProperty } from "./serverProperty.svelte";
import type { Task } from "./task";
import type { TaskState } from "./taskState";


export interface SubTask extends Item {
    task: Task;
    taskStateID: WriteOnlyServerProperty<number>;
    taskState: Readable<TaskState>;
    creator?: Creator;
    instanceIds: FilterList<number>;
}

const taskStateID = {
    toValue: (params: any) => {
        const endpoint = `subtasks/${params.SubTaskID}/taskstateid`;
        const mediaType = 'application/json';
        const initialValue = params.TaskStateID;
        return new WriteOnlyServerProperty<any>({ endpoint, mediaType, initialValue });
    },
    toParam: (params: any, value: WriteOnlyServerProperty<number>) => value.value
};

export const SubTaskConstructor = new ItemConstructor<SubTask>(
    'SubTaskID', {
    task: FKMapping('TaskID', 'tasks'),
    taskStateID,
    taskState: new DerivedProperty((self: SubTask, data: DataModel) => derived(self.taskStateID, () => data.taskStates.get(self.taskStateID.value!))),
    creator: FKMapping('CreatorID', 'creators'),
    instanceIds: new DerivedProperty((self: SubTask, data: DataModel) => data.subTaskImageLinks.filter(link => link.subTask === self).map(link => link.instanceid)),
    // subtaskimagelinks: new DerivedProperty((self: SubTask, data: DataModel) => data.subTaskImageLinks.filter(link => link.subTask === self)),
});