import { BaseItem } from "./itemList";

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
    stateId!: number;
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
}