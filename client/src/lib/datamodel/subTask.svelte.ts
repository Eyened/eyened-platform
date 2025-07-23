import { apiUrl } from "$lib/config";
import type { Creator } from "./creator.svelte";
import type { Instance } from "./instance.svelte";
import { BaseItem, BaseLinkingItem, FilterList } from "./itemList";
import { data, removeData } from "./model";
import type { Task } from "./task.svelte";
import type { TaskState } from "./taskState";

export interface ServerSubTask {
    SubTaskID: number;
    TaskID: number;
    TaskStateID: number;
    CreatorID: number;
    Comments: string;
}

export class SubTask extends BaseItem {
    static endpoint = 'sub-tasks';

    static mapping = {
        'TaskID': 'taskId',
        'TaskStateID': 'taskStateId',
        'CreatorID': 'creatorId',
        'Comments': 'comments'
    };

    id!: number;
    taskId!: number;
    taskStateId: number = $state(0);
    creatorId!: number;
    comments?: string = $state();

    constructor(item: ServerSubTask) {
        super();
        this.init(item);
    }

    init(item: ServerSubTask) {
        this.id = item.SubTaskID;
        this.taskId = item.TaskID;
        this.taskStateId = item.TaskStateID;
        this.creatorId = item.CreatorID;
        this.comments = item.Comments;
    }

    get task(): Task {
        return data.tasks.get(this.taskId)!;
    }
    state: TaskState = $derived(data.taskStates.get(this.taskStateId)!);
    creator: Creator = $derived(data.creators.get(this.creatorId)!);

    get instances(): FilterList<Instance> {
        return data.subTaskImageLinks
            .filter(link => link.subTaskId === this.id)
            .map(link => data.instances.get(link.instanceId)!);
    }
}
export interface ServerSubTaskImageLink {
    SubTaskID: number;
    ImageInstanceID: number;
}
export class SubTaskImageLink extends BaseLinkingItem {
    static endpoint = 'sub-task-image-links';
    static parentResource = 'sub-tasks';
    static childResource = 'image-links';
    static parentIdField = 'subTaskId';
    static childIdField = 'instanceId';
    static mapping = {
        'SubTaskID': 'subTaskId',
        'ImageInstanceID': 'instanceId'
    };
    id!: string;

    constructor(item: ServerSubTaskImageLink) {
        super(item.SubTaskID, item.ImageInstanceID);
        this.init(item);
    }

    get subTaskId(): number {
        return this.parentId;
    }
    get instanceId(): number {
        return this.childId;
    }

    init(item: ServerSubTaskImageLink) {
        this.id = `${item.SubTaskID}_${item.ImageInstanceID}`;
    }
}