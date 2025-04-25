import { ItemCollection, MutableItemCollection } from "./itemList";

import { AnnotationConstructor, type Annotation } from "./annotation";
import { AnnotationDataConstructor, type AnnotationData } from "./annotationData";
import { AnnotationTypeConstructor, type AnnotationType } from "./annotationType";
import { CreatorConstructor, type Creator } from "./creator";
import { DeviceConstructor, DeviceModelConstructor, type Device, type DeviceModel } from "./device";
import { FeatureConstructor, type Feature } from "./feature";
import { FormAnnotationConstructor, type FormAnnotation } from "./formAnnotation";
import { FormSchemaConstructor, type FormSchema } from "./formSchema";
import { InstanceConstructor, type Instance } from "./instance";
import { PatientConstructor, type Patient } from "./patient";
import { ProjectConstructor, type Project } from "./project";
import { ScanConstructor, type Scan } from "./scan";
import { SeriesConstructor, type Series } from "./series";
import { StudyConstructor, type Study } from "./study";
import { SubTaskConstructor, type SubTask } from "./subTask";
import { SubTaskImageLinkConstructor, type SubTaskImageLink } from "./subTaskImageLink";
import { AnnotationTagConstructor, InstanceTagConstructor, StudyTagConstructor, TagConstructor, type AnnotationTag, type InstanceTag, type StudyTag, type Tag } from "./tag";
import { TaskConstructor, type Task } from "./task";
import { TaskDefinitionConstructor, type TaskDefinition } from "./taskDefinition";
import { TaskStateConstructor, type TaskState } from "./taskState";

export const constructors = {
    annotationDatas: AnnotationDataConstructor,
    annotations: AnnotationConstructor,
    annotationTypes: AnnotationTypeConstructor,

    creators: CreatorConstructor,
    devices: DeviceConstructor,
    deviceModels: DeviceModelConstructor,
    features: FeatureConstructor,
    formAnnotations: FormAnnotationConstructor,
    formSchemas: FormSchemaConstructor,

    instances: InstanceConstructor,
    patients: PatientConstructor,
    projects: ProjectConstructor,
    scans: ScanConstructor,
    series: SeriesConstructor,
    studies: StudyConstructor,


    taskDefinitions: TaskDefinitionConstructor,
    tasks: TaskConstructor,
    taskStates: TaskStateConstructor,
    subTasks: SubTaskConstructor,
    subTaskImageLinks: SubTaskImageLinkConstructor,

    tags: TagConstructor,
    instanceTags: InstanceTagConstructor,
    studyTags: StudyTagConstructor,
    annotationTags: AnnotationTagConstructor,
};

export class DataModel {

    annotationDatas = new MutableItemCollection<AnnotationData>('annotationDatas');
    annotations = new MutableItemCollection<Annotation>('annotations');
    annotationTypes = new ItemCollection<AnnotationType>();

    creators = new ItemCollection<Creator>();
    devices = new ItemCollection<Device>();
    deviceModels = new ItemCollection<DeviceModel>();
    features = new MutableItemCollection<Feature>('features');
    formAnnotations = new MutableItemCollection<FormAnnotation>('formAnnotations');
    formSchemas = new ItemCollection<FormSchema>();

    instances = new ItemCollection<Instance>();
    patients = new ItemCollection<Patient>();
    projects = new ItemCollection<Project>();
    scans = new ItemCollection<Scan>();
    series = new ItemCollection<Series>();
    studies = new ItemCollection<Study>();

    taskDefinitions = new MutableItemCollection<TaskDefinition>('taskDefinitions');
    tasks = new MutableItemCollection<Task>('tasks');
    taskStates = new ItemCollection<TaskState>();
    subTasks = new MutableItemCollection<SubTask>('subTasks');
    subTaskImageLinks = new MutableItemCollection<SubTaskImageLink>('subTaskImageLinks');

    tags = new MutableItemCollection<Tag>('tags');
    instanceTags = new MutableItemCollection<InstanceTag>('instanceTags');
    studyTags = new MutableItemCollection<StudyTag>('studyTags');
    annotationTags = new MutableItemCollection<AnnotationTag>('annotationTags');
}
export const data = new DataModel();

export function instanceTags(instance: Instance) {
    return data.instanceTags.filter(it => it.instance === instance);
}

export function annotationDatas(annotation: Annotation) {
    return data.annotationDatas.filter(a => a.annotation.id === annotation.id);
}

export function instanceAnnotations(instance: Instance) {
    return data.annotations.filter(a => a.instance === instance);
}
export function clearData() {
    data['instances'].clear();
    data['series'].clear();
    data['studies'].clear();
    data['patients'].clear();
    data['annotationDatas'].clear();
    data['annotations'].clear();
    data['formAnnotations'].clear();
    
}
export function importData(itemCollections: { [key: string]: any[] }) {

    const newData: { [key: string]: Map<string | number, any> } = {};
    const allNewItems = [];
    // First pass: create all new objects with only the id
    for (const [key, items] of Object.entries(itemCollections)) {

        if (!(key in data)) {
            console.warn(`No collection for ${key}`);
            continue;
        }
        const collection = data[key];
        const constructor = constructors[key];
        const newItems = [];
        for (const itemData of items) {
            const id = constructor.getID(itemData);
            if (collection.get(id)) {
                // item already exists
                continue;
            }
            // create new object with just the id            
            const newItem = constructor.create(itemData);
            newItems.push(newItem);
            let newItemMap = newData[key];
            if (!newItemMap) {
                newItemMap = new Map<string | number, any>();
                newData[key] = newItemMap;
            }
            newItemMap.set(id, newItem);
            allNewItems.push([newItem, itemData, constructor]);
        }
    }

    // initialize full objects (resolves FKs)
    for (const [item, itemData, constructor] of allNewItems) {
        constructor.toItem(item, itemData, data, newData);

    }
    for (const [key, map] of Object.entries(newData)) {
        const collection = data[key as keyof DataModel];
        const newItems = Array.from(map.values());
        collection.importItems(newItems);
    }
}

export function importItem(key: string, itemData: any) {
    const constructor = constructors[key];
    const collection = data[key];
    const id = constructor.getID(itemData);
    if (collection.get(id)) {
        throw new Error(`Item with id ${id} already exists`);
    }
    const newItem = constructor.create(itemData);
    constructor.toItem(newItem, itemData, data, {});
    collection.importItems([newItem]);
    return newItem;
}

export async function createFormAnnotation(creator: Creator, instance: Instance, formSchema: FormSchema, subTask?: SubTask): Promise<FormAnnotation> {
    const item: any = {
        formSchema,
        patient: instance.patient,
        study: instance.study,
        instance,
        creator,
        subTask
    };
    const result = await data.formAnnotations.create(item);
    await result.value.setValue({});
    return result;
}

