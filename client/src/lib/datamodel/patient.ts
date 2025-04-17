import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";
import { DateMapping, FKMapping } from "./mapping";
import type { Project } from "./project";

export interface Patient extends Item {
    id: number,
    identifier: string,
    project: Project,
    birthDate?: Date,
    sex?: 'M' | 'F',
    isHuman: boolean
}

export const PatientConstructor = new ItemConstructor<Patient>(
    'PatientID', {
    identifier: 'PatientIdentifier',
    project: FKMapping('ProjectID', 'projects'),
    birthDate: DateMapping('BirthDate'),
    sex: 'Sex',
    isHuman: 'isHuman'
});