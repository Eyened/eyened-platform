import type { BaseItem } from "./baseItem";
import type { CompositeFeature } from "./compositeFeature.svelte";
import type { Contact } from "./contact.svelte";
import type { Creator } from "./creator.svelte";
import type { Device, DeviceModel } from "./device.svelte";
import type { Feature } from "./feature.svelte";
import type { FormAnnotation } from "./formAnnotation.svelte";
import type { FormSchema } from "./formSchema.svelte";
import type { Instance } from "./instance.svelte";
import { ItemCollection } from "./itemList";
import type { Patient } from "./patient";
import type { Project } from "./project.svelte";
import type { Scan } from "./scan";
import type { Segmentation } from "./segmentation.svelte";
import type { Series } from "./series";
import type { Study } from "./study";
import type { SubTask, SubTaskImageLink } from "./subTask.svelte";
import type { AnnotationTag, InstanceTag, Tag } from "./tag";
import type { Task } from "./task.svelte";
import type { TaskDefinition } from "./taskDefinition";
import type { TaskState } from "./taskState";

export const data: {
    compositeFeatures: ItemCollection<CompositeFeature>;
    'composite-features': ItemCollection<CompositeFeature>;
    formAnnotations: ItemCollection<FormAnnotation>;
    'form-annotations': ItemCollection<FormAnnotation>;
    formSchemas: ItemCollection<FormSchema>;
    'form-schemas': ItemCollection<FormSchema>;
    deviceModels: ItemCollection<DeviceModel>;
    'device-models': ItemCollection<DeviceModel>;
    taskDefinitions: ItemCollection<TaskDefinition>;
    'task-definitions': ItemCollection<TaskDefinition>;
    taskStates: ItemCollection<TaskState>;
    'task-states': ItemCollection<TaskState>;
    subTasks: ItemCollection<SubTask>;
    'sub-tasks': ItemCollection<SubTask>;
    subTaskImageLinks: ItemCollection<SubTaskImageLink>;
    'sub-task-image-links': ItemCollection<SubTaskImageLink>;
    instances: ItemCollection<Instance>;
    series: ItemCollection<Series>;
    studies: ItemCollection<Study>;
    patients: ItemCollection<Patient>;
    segmentations: ItemCollection<Segmentation>;
    creators: ItemCollection<Creator>;
    contacts: ItemCollection<Contact>;
    projects: ItemCollection<Project>;
    devices: ItemCollection<Device>;
    features: ItemCollection<Feature>;
    scans: ItemCollection<Scan>;
    tasks: ItemCollection<Task>;
    tags: ItemCollection<Tag>;
    annotationTags: ItemCollection<AnnotationTag>;
    instanceTags: ItemCollection<InstanceTag>;
} = { } as any;

const constructors: { [key: string]: (new (item: any) => BaseItem) } = {};

export function registerConstructor(key: string, constructor: any) {
    const keyCamel = key.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    constructors[key] = constructor;
    constructors[keyCamel] = constructor;
    data[keyCamel] = new ItemCollection<InstanceType<typeof constructor>>();
    data[key] = data[keyCamel];
}

function initializeModel() {
    // Import all model classes - this will trigger their registerConstructor calls
    import('./scan');
    import('./patient');
    import('./study');
    import('./series');
    import('./instance.svelte');
    import('./project.svelte');
    import('./device.svelte');
    import('./creator.svelte');
    import('./contact.svelte');
    import('./compositeFeature.svelte');
    import('./feature.svelte');
    import('./formSchema.svelte');
    import('./formAnnotation.svelte');
    import('./segmentation.svelte');
    import('./task.svelte');
    import('./taskDefinition');
    import('./taskState');
    import('./subTask.svelte');
    import('./tag');
}
initializeModel();

export function clearData() {
    data.instances.clear();
    data.series.clear();
    data.studies.clear();
    data.patients.clear();
    data.formAnnotations.clear();
}

export function removeData(items: { [key: string]: number[] }) {
    for (const [key, ids] of Object.entries(items)) {
        const collection = data[key as keyof typeof data];
        for (const id of ids) {
            collection.delete(id);
        }
    }
}

export function importData(itemCollections: { [key: string]: any[] }) {
    const resp = {};
    for (const [key, items] of Object.entries(itemCollections)) {
        if (!(key in constructors)) {
            console.error(`Unknown key: ${key}`);
            continue;
        }
        const collection = data[key as keyof typeof data];
        const cstr = constructors[key as keyof typeof constructors];
        const newItems = items.map(item => new cstr(item));
        collection.importItems(newItems);
        resp[key] = newItems;
    }
    return resp;
}
