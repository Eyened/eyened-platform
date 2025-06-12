import { BaseItem } from "./itemList";

export interface ServerSubTask {
    SubTaskID: number;
    TaskID: number;
    TaskStateID: number;
    CreatorID: number;
    Comments: string;
    InstanceIds: number[];
}

export class SubTask extends BaseItem {
    static endpoint = 'subtasks';

    static mapping = {
        'TaskID': 'taskId',
        'TaskStateID': 'taskStateId',
        'CreatorID': 'creatorId',
        'Comments': 'comments',
        'InstanceIds': 'instanceIds',
    };

    id!: number;
    taskId!: number;
    taskStateId!: number;
    creatorId!: number;
    comments!: string;    

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
}

// const taskStateID = {
//     toValue: (params: any) => {
//         const endpoint = `subtasks/${params.SubTaskID}/taskstateid`;
//         const initialValue = params.TaskStateID;
//         return new WriteOnlyServerProperty<any>({ endpoint, initialValue });
//     },
//     toParam: (params: any, value: WriteOnlyServerProperty<number>) => value.value
// };

// export const SubTaskConstructor = new ItemConstructor<SubTask>(
//     'SubTaskID', {
//     task: FKMapping('TaskID', 'tasks'),
//     taskStateID,
//     taskState: new DerivedProperty((self: SubTask, data: DataModel) => derived(self.taskStateID, () => data.taskStates.get(self.taskStateID.value!))),
//     creator: FKMapping('CreatorID', 'creators'),
//     comments: 'Comments',
//     instanceIds: new DerivedProperty((self: SubTask, data: DataModel) => data.subTaskImageLinks.filter(link => link.subTask === self).map(link => link.instanceid)),
//     // subtaskimagelinks: new DerivedProperty((self: SubTask, data: DataModel) => data.subTaskImageLinks.filter(link => link.subTask === self)),
// });