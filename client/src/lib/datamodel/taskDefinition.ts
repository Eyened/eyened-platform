import { BaseItem } from "./itemList";

export interface ServerTaskDefinition {
    TaskDefinitionID: number;
    TaskDefinitionName: string;
    TaskConfig: Record<string, any> | null;
}

export class TaskDefinition extends BaseItem {
    static endpoint = 'task-definitions';
    static mapping = {
        'TaskDefinitionName': 'name',
        'TaskConfig': 'config',
    };

    id!: number;
    name!: string;
    config!: Record<string, any> | null;

    constructor(item: ServerTaskDefinition) {
        super();
        this.init(item);
    }

    init(item: ServerTaskDefinition) {
        this.id = item.TaskDefinitionID;
        this.name = item.TaskDefinitionName;
        this.config = item.TaskConfig;
    }
}