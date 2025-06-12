import { BaseItem, type FilterList } from "./itemList";
import type { Study } from "./study";
import { data } from "./model";

export interface ServerPatient {
    PatientID: number,
    PatientIdentifier: string,
    ProjectID: number,
    BirthDate?: Date,
    Sex?: 'M' | 'F',
    IsHuman: boolean,
}
export class Patient extends BaseItem {
    static endpoint = 'patients';
    static mapping = {
        'PatientIdentifier': 'identifier',
        'ProjectID': 'projectId',
        'BirthDate': 'birthDate',
        'Sex': 'sex',
        'IsHuman': 'isHuman',
    };

    id!: number;
    identifier!: string;
    projectId!: number;
    birthDate?: Date;
    sex?: 'M' | 'F';
    isHuman!: boolean;

    constructor(item: ServerPatient) {
        super();
        this.init(item);
    }

    init(item: ServerPatient) {
        this.id = item.PatientID;
        this.identifier = item.PatientIdentifier;
        this.projectId = item.ProjectID;
        this.birthDate = item.BirthDate;
        this.sex = item.Sex;
        this.isHuman = item.IsHuman;
    }

    get studies(): FilterList<Study> {
        return data.studies.filter(study => study.patientId == this.id);
    }
}