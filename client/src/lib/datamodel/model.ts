import { BaseItem, ItemCollection } from "./itemList";

import { Contact } from "./contact.svelte";
import { Creator } from "./creator.svelte";
import { Project } from "./project.svelte";
import { Patient } from "./patient";
import { Instance } from "./instance.svelte";
import { Series } from "./series";
import { Study } from "./study";
import { AnnotationData } from "./annotationData.svelte";
import { Annotation } from "./annotation.svelte";
import { FormAnnotation } from "./formAnnotation.svelte";
import { Device } from "./device.svelte";
import { DeviceModel } from "./device.svelte";
import { FormSchema } from "./formSchema.svelte";
import { AnnotationType, AnnotationTypeFeature } from "./annotationType";
import { Feature } from "./feature.svelte";
import { Scan } from "./scan";
import { TaskDefinition } from "./taskDefinition";
import { TaskState } from "./taskState";
import { Task } from "./task.svelte";
import { SubTask } from "./subTask.svelte";
import { SubTaskImageLink } from "./subTask.svelte";

export const itemClassMap = {
    creators: Creator,
    contacts: Contact,
    projects: Project,
    instances: Instance,
    series: Series,
    studies: Study,
    patients: Patient,
    "annotation-data": AnnotationData,
    annotations: Annotation,
    "annotation-types": AnnotationType,
    "annotation-type-features": AnnotationTypeFeature,
    "form-annotations": FormAnnotation,
    "form-schemas": FormSchema,
    "device-models": DeviceModel,
    devices: Device,
    features: Feature,
    scans: Scan,
    "tasks": Task,
    "task-definitions": TaskDefinition,
    "task-states": TaskState,
    "sub-tasks": SubTask,
    "sub-task-image-links": SubTaskImageLink,
} as const;
type ItemClassMap = typeof itemClassMap;

type DataModel = {
    [K in keyof ItemClassMap]: ItemCollection<InstanceType<ItemClassMap[K]>>
};

export const data: DataModel & {
    annotationData: ItemCollection<AnnotationData>;
    annotationTypes: ItemCollection<AnnotationType>;
    annotationTypeFeatures: ItemCollection<AnnotationTypeFeature>;
    formAnnotations: ItemCollection<FormAnnotation>;
    formSchemas: ItemCollection<FormSchema>;
    deviceModels: ItemCollection<DeviceModel>;
    taskDefinitions: ItemCollection<TaskDefinition>;
    taskStates: ItemCollection<TaskState>;
    subTasks: ItemCollection<SubTask>;
    subTaskImageLinks: ItemCollection<SubTaskImageLink>;
} = {
    ...Object.fromEntries(
        Object.entries(itemClassMap).map(([key, cls]) => [key, new ItemCollection()])
    ),
    // camelCase aliases
    annotationData: undefined!,
    annotationTypes: undefined!,
    annotationTypeFeatures: undefined!,
    formAnnotations: undefined!,
    formSchemas: undefined!,
    deviceModels: undefined!,
    taskDefinitions: undefined!,
    taskStates: undefined!,
    subTasks: undefined!,
    subTaskImageLinks: undefined!,
} as any;

// link aliases after creation
data.annotationData = data["annotation-data"];
data.annotationTypes = data["annotation-types"];
data.annotationTypeFeatures = data["annotation-type-features"];
data.formAnnotations = data["form-annotations"];
data.formSchemas = data["form-schemas"];
data.deviceModels = data["device-models"];
data.taskDefinitions = data["task-definitions"];
data.taskStates = data["task-states"];
data.subTasks = data["sub-tasks"];
data.subTaskImageLinks = data["sub-task-image-links"];

export function clearData() {
    data.instances.clear();
    data.series.clear();
    data.studies.clear();
    data.patients.clear();
    data.annotationData.clear();
    data.annotations.clear();
    data.formAnnotations.clear();
}

export function removeData(items: { [key: string]: number[] }) {
    for (const [key, ids] of Object.entries(items)) {
        const collection = data[key as keyof DataModel];
        for (const id of ids) {
            collection.delete(id);
        }
    }

}
export function importData(itemCollections: { [key: string]: any[] }) {
    console.log('importing data', itemCollections);
    for (const [key, items] of Object.entries(itemCollections)) {
        if (!(key in itemClassMap)) {
            console.error(`Unknown key: ${key}`);
            continue;
        }
        const collection = data[key];
        const cstr = itemClassMap[key];
        collection.importItems(items.map(item => new cstr(item)));
    }
    console.log(data);
}