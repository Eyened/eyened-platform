import openapi from "../../types/openapi.json";
import type { TaskState } from "../../types/openapi_types";

type OpenApiWithTaskState = {
    components: { schemas: { TaskState: { enum: TaskState[] } } };
};

export const TASK_STATE_OPTIONS = (openapi as OpenApiWithTaskState).components
    .schemas.TaskState.enum;
