import { BaseItem } from "./itemList";

export interface ServerTaskDefinition {
    TaskDefinitionID: number;
    TaskDefinitionName: string;
}

export class TaskDefinition extends BaseItem {
    static endpoint = 'taskDefinitions';
    static mapping = {
        'TaskDefinitionName': 'name',
    };

    id!: number;
    name!: string;

    constructor(item: ServerTaskDefinition) {
        super();
        this.init(item);
    }

    init(item: ServerTaskDefinition) {
        this.id = item.TaskDefinitionID;
        this.name = item.TaskDefinitionName;
    }
}