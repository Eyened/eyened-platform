import type { SubTask } from './datamodel/subTask.svelte';
import type { Task } from './datamodel/task.svelte';
import type { Color } from './utils';

export type int = number;
export type img_id = string;

export type FilterFieldSpec =
    | 'VARCHAR'
    | 'INTEGER'
    | 'BOOLEAN'
    | 'FLOAT'
    | 'DATE'
    | number[]
    | string[];

export type Keypoints = {
    fovea_xy: [number, number],
    disc_edge_xy: [number, number],
    prep_fovea_xy: [number, number],
    prep_disc_edge_xy: [number, number]
}

export interface TaskContext {
    task: Task;
    subTask: SubTask;
    subTaskIndex: number;
    taskConfig: any;
}

export interface Position2D {
    x: number;
    y: number;
}
export interface Position extends Position2D {
    index: number;
}
export type ImageLocation = {
    location: Position2D;
    image: string;
};
export interface ETDRSCoordinates {
    disc_edge: Position2D;
    fovea: Position2D;
}
export type Branch = {
    id: string;
    drawing: string;
    vesselType: 'Artery' | 'Vein' | 'Vessel';
    color?: Color;
};

