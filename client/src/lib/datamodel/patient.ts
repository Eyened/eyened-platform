import { ItemConstructor } from "./itemContructor";
import type { FilterList, Item } from "./itemList";
import { DateMapping, FKMapping } from "./mapping";
import type { Project } from "./project";
import type { Study } from "./study";
import type { DataModel } from './model';
import { DerivedProperty } from "./itemContructor";

export interface Patient extends Item {
    id: number,
    identifier: string,
    project: Project,
    birthDate?: Date,
    sex?: 'M' | 'F',
    isHuman: boolean,
    studies: FilterList<Study>
}

export const PatientConstructor = new ItemConstructor<Patient>(
    'PatientID', {
    identifier: 'PatientIdentifier',
    project: FKMapping('ProjectID', 'projects'),
    birthDate: DateMapping('BirthDate'),
    sex: 'Sex',
    isHuman: 'isHuman',
    studies: new DerivedProperty((self: Patient, data: DataModel) => data.studies.filter(study => study.patient == self)),
});