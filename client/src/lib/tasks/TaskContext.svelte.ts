import type { SubTaskWithImagesGET, TaskGET } from '../../types/openapi_types';


export interface TaskContext {
    task: TaskGET;
    subTask: SubTaskWithImagesGET;
    subTaskIndex: number;
    taskConfig: any;
}
