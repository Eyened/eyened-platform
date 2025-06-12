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
import { FormAnnotation } from "./formAnnotation";
import { Device } from "./device.svelte";
import { DeviceModel } from "./device.svelte";
import { FormSchema } from "./formSchema.svelte";
import { AnnotationType, AnnotationTypeFeature } from "./annotationType";
import { Feature } from "./feature.svelte";
import { Scan } from "./scan";

export class DataModel {
    creators = new ItemCollection<Creator>();
    contacts = new ItemCollection<Contact>();
    projects = new ItemCollection<Project>();
    instances = new ItemCollection<Instance>();
    series = new ItemCollection<Series>();
    studies = new ItemCollection<Study>();
    patients = new ItemCollection<Patient>();
    'annotation-data' = new ItemCollection<AnnotationData>();
    annotationData = this['annotation-data'];

    annotations = new ItemCollection<Annotation>();
    annotationTypes = new ItemCollection<AnnotationType>();
    annotationTypeFeatures = new ItemCollection<AnnotationTypeFeature>();
    'form-annotations' = new ItemCollection<FormAnnotation>();
    formAnnotations = this['form-annotations'];
    formSchemas = new ItemCollection<FormSchema>();
    devices = new ItemCollection<Device>();
    deviceModels = new ItemCollection<DeviceModel>();
    features = new ItemCollection<Feature>();
    scans = new ItemCollection<Scan>();
}
const constructors: { [key: string]: (new (item: any) => BaseItem) } = {
    creators: Creator,
    contacts: Contact,
    projects: Project,
    instances: Instance,
    series: Series,
    studies: Study,
    patients: Patient,
    'annotation-data': AnnotationData,
    annotations: Annotation,
    'form-annotations': FormAnnotation,
    formSchemas: FormSchema,
    devices: Device,
    deviceModels: DeviceModel,
    annotationTypes: AnnotationType,
    annotationTypeFeatures: AnnotationTypeFeature,
    features: Feature,
    scans: Scan
}

export const data = new DataModel();

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
        if (key in constructors) {
            data[key as keyof DataModel].importItems(items.map(item => new constructors[key](item)));
        }
    }
    console.log(data);
}