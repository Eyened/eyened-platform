import openapi from "../../types/openapi.json";
import type { TaskState } from "../../types/openapi_types";

export const TASK_STATE_OPTIONS = (openapi as any).components.schemas.TaskState
	.enum as TaskState[];
