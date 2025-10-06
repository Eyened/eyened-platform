import openapi from './openapi.json';
import type { SubTaskState, TaskState } from './openapi_types';

export const searchOrderBy = openapi.components.schemas.SearchQuery.properties.order_by.enum
export const studiesSearchOrderBy = openapi.components.schemas.StudySearchQuery.properties.order_by.enum
export const taskStates = openapi.components.schemas.TaskState.enum as TaskState[]
export const subTaskStates = openapi.components.schemas.SubTaskState.enum as SubTaskState[]