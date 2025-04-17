import type { Component } from 'svelte';
import type { SubTask } from './datamodel/subTask';
import type { Task } from './datamodel/task';
import type { Color } from './utils';

export type int = number;
export type img_id = string;
export type Laterality = 'L' | 'R';

export type FilterFieldSpec =
    | 'VARCHAR'
    | 'INTEGER'
    | 'BOOLEAN'
    | 'FLOAT'
    | 'DATE'
    | number[]
    | string[];

export interface Condition {
    variable: string;
    operator: string;
    value: string;
}

export type DialogueType = undefined | string | {
    query: string | Component,
    props?: any,
    approve: string,
    decline: string,
    resolve: () => any,
    reject: () => any
}

export type AnnotationTypeName =
    | 'Segmentation 2D'
    | 'Segmentation OCT B-scan'
    | 'Segmentation OCT Volume'
    | 'Segmentation OCT Enface'
    | 'ETDRS grid coordinates'
    | 'Registration point set'
    | 'Registration'
    | 'Grading form'
    | 'Grading coordinate'
    | 'Segmentation 2D masked'
    | 'Bounding Box';

export type AnnotationTypeInterpretation = '' | 'R/G mask' | 'Binary mask' | 'Label numbers' | 'Probability' | 'Layer bits';
export type AnnotationType = {
    AnnotationTypeID: number;
    AnnotationTypeName: AnnotationTypeName;
    Interpretation: AnnotationTypeInterpretation;
};
export interface Patient {
    PatientID: int;
    PatientIdentifier: string;
    BirthDate: Date;
    Sex: 'M' | 'F' | null;
    ProjectName: string;
}
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
export interface ROI {
    cx: number;
    cy: number;
    radius: number;
    min_x: number;
    max_x: number;
    min_y: number;
    max_y: number;
    w: number;
    h: number;
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
