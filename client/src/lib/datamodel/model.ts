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


export class DataModel {

    annotationDatas = new MutableItemCollection<AnnotationData>('annotation-data', AnnotationDataConstructor);
    'annotation-data': MutableItemCollection<AnnotationData> = this.annotationDatas;

    annotations = new MutableItemCollection<Annotation>('annotations', AnnotationConstructor);

    annotationTypes = new ItemCollection<AnnotationType>('annotation-types', AnnotationTypeConstructor);
    'annotation-types': ItemCollection<AnnotationType> = this.annotationTypes;

    creators = new ItemCollection<Creator>('creators', CreatorConstructor);
    devices = new ItemCollection<Device>('devices', DeviceConstructor);
    deviceModels = new ItemCollection<DeviceModel>('device-models', DeviceModelConstructor);
    'device-models': ItemCollection<DeviceModel> = this.deviceModels;

    features = new MutableItemCollection<Feature>('features', FeatureConstructor);
    formAnnotations = new MutableItemCollection<FormAnnotation>('form-annotations', FormAnnotationConstructor);
    'form-annotations': MutableItemCollection<FormAnnotation> = this.formAnnotations;
    formSchemas = new ItemCollection<FormSchema>('form-schemas', FormSchemaConstructor);
    'form-schemas': ItemCollection<FormSchema> = this.formSchemas;

    instances = new ItemCollection<Instance>('instances', InstanceConstructor);
    patients = new ItemCollection<Patient>('patients', PatientConstructor);
    projects = new ItemCollection<Project>('projects', ProjectConstructor);
    scans = new ItemCollection<Scan>('scans', ScanConstructor);
    series = new ItemCollection<Series>('series', SeriesConstructor);
    studies = new ItemCollection<Study>('studies', StudyConstructor);

    taskDefinitions = new MutableItemCollection<TaskDefinition>('task-definitions', TaskDefinitionConstructor);
    'task-definitions': MutableItemCollection<TaskDefinition> = this.taskDefinitions;
    tasks = new MutableItemCollection<Task>('tasks', TaskConstructor);
    taskStates = new ItemCollection<TaskState>('task-states', TaskStateConstructor);
    'task-states': ItemCollection<TaskState> = this.taskStates;
    subTasks = new MutableItemCollection<SubTask>('sub-tasks', SubTaskConstructor);
    'sub-tasks': MutableItemCollection<SubTask> = this.subTasks;
    subTaskImageLinks = new MutableItemCollection<SubTaskImageLink>('sub-task-image-links', SubTaskImageLinkConstructor);
    'sub-task-image-links': MutableItemCollection<SubTaskImageLink> = this.subTaskImageLinks;

    tags = new MutableItemCollection<Tag>('tags', TagConstructor);
    instanceTags = new MutableItemCollection<InstanceTag>('instance-tags', InstanceTagConstructor);
    'instance-tags': MutableItemCollection<InstanceTag> = this.instanceTags;
    studyTags = new MutableItemCollection<StudyTag>('study-tags', StudyTagConstructor);
    'study-tags': MutableItemCollection<StudyTag> = this.studyTags;
    annotationTags = new MutableItemCollection<AnnotationTag>('annotation-tags', AnnotationTagConstructor);
    'annotation-tags': MutableItemCollection<AnnotationTag> = this.annotationTags;
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
        const constructor = collection.itemConstructor;
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
    const collection = data[key as keyof DataModel];
    const constructor = collection.itemConstructor;
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

