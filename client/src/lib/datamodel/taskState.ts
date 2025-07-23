import { BaseItem } from "./itemList";

export interface ServerTaskState {
    TaskStateID: number;
    TaskStateName: string;
}

export class TaskState extends BaseItem {
    static endpoint = 'taskStates';
    static mapping = {
        'TaskStateName': 'name',
    };

    id!: number;
    name!: string;

    constructor(item: ServerTaskState) {
        super();
        this.init(item);
    }

    init(item: ServerTaskState) {
        this.id = item.TaskStateID;
        this.name = item.TaskStateName;
    }
}