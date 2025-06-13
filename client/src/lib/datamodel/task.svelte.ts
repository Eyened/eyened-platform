import { BaseItem, FilterList } from "./itemList";
import { data } from "./model";
import type { SubTask } from "./subTask.svelte";
import type { TaskState } from "./taskState";

export interface ServerTask {
    TaskID: number;
    TaskName: string;
    TaskDefinitionID: number;
    TaskStateID: number;
    DateInserted: Date;
    Description?: string;
}
export class Task extends BaseItem {
    static endpoint = 'tasks';
    static mapping = {
        'TaskName': 'name',
        'TaskDefinitionID': 'definitionId',
        'TaskStateID': 'stateId',
        'DateInserted': 'dateInserted',
        'Description': 'description',
    };

    id!: number;
    name!: string;
    definitionId!: number;
    stateId: number = $state(0);
    dateInserted!: Date;
    description?: string = $state(undefined);

    constructor(item: ServerTask) {
        super();
        this.init(item);
    }

    init(item: ServerTask) {
        this.id = item.TaskID;
        this.name = item.TaskName;
        this.definitionId = item.TaskDefinitionID;
        this.stateId = item.TaskStateID;
        this.dateInserted = item.DateInserted;
        this.description = item.Description;
    }

    state: TaskState = $derived(data.taskStates.get(this.stateId)!);

    get subTasks(): FilterList<SubTask> {
        return data.subTasks.filter(subTask => subTask.taskId === this.id);
    }
}