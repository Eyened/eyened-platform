
import type { Annotation } from "./annotation";
import type { Instance } from "./instance";
import { DerivedProperty, ItemConstructor } from "./itemContructor";
import type { FilterList, Item } from "./itemList";
import { DateMapping, FKMapping } from "./mapping";
import type { DataModel } from "./model";
import type { Patient } from "./patient";
import type { Series } from "./series";
import type { Tag } from "./tag";

export interface Study extends Item {
    id: number,
    patient: Patient,
    description?: string | null,
    date: Date,
    StudyInstanceUid: string,
    instances: FilterList<Instance>,
    series: FilterList<Series>,
    tags: FilterList<Tag>,
    annotations: FilterList<Annotation>,
};

export const StudyConstructor = new ItemConstructor<Study>(
    'StudyID', {
    patient: FKMapping('PatientID', 'patients'),
    description: 'StudyDescription',
    date: DateMapping('StudyDate'),
    StudyInstanceUid: 'StudyInstanceUid',

    instances: new DerivedProperty((self: Study, data: DataModel) => data.instances.filter(instance => instance.study == self)),
    series: new DerivedProperty((self: Study, data: DataModel) => data.series.filter(series => series.study == self)),
    tags: new DerivedProperty((self: Study, data: DataModel) => data.studyTags.filter(studyTag => studyTag.study == self)),
    annotations: new DerivedProperty((self: Study, data: DataModel) => data.annotations.filter(annotation => annotation.study == self))
});
