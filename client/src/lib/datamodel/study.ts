
import type { Annotation } from "./annotation.svelte";
import type { Instance } from "./instance.svelte";
import { BaseItem, parseDate, type FilterList } from "./itemList";
import { data } from "./model";
import type { Patient } from "./patient";
import type { Series } from "./series";
import type { Tag } from "./tag";

export interface ServerStudy {
    StudyID: number;
    PatientID: number;
    StudyDescription: string;
    StudyDate: string;
    StudyInstanceUid: string;
}

export class Study extends BaseItem {
    static endpoint = 'studies';
    static mapping = {
        'PatientID': 'patientId',
        'StudyDescription': 'description',
        'StudyDate': 'date',
        'StudyInstanceUid': 'instanceUID',
    };


    id!: number;
    patientId!: number;
    description?: string;
    date!: Date;
    instanceUID!: string;

    constructor(item: ServerStudy) {
        super();
        this.init(item);
    }

    init(item: ServerStudy) {
        this.id = item.StudyID;
        this.patientId = item.PatientID;
        this.description = item.StudyDescription;
        this.date = parseDate(item.StudyDate);
        this.instanceUID = item.StudyInstanceUid;
    }
    get patient(): Patient {
        return data.patients.get(this.patientId)!;
    }
    get instances(): FilterList<Instance> {
        return data.images.filter(instance => instance.series.studyId == this.id);
    }
    get series(): FilterList<Series> {
        return data.series.filter(series => series.studyId == this.id);
    }
    get tags(): FilterList<Tag> {
        return data.tags.filter(tag => tag.study_id == this.id);
    }
    get annotations(): FilterList<Annotation> {
        return data.annotations.filter(annotation => annotation.studyId == this.id);
    }
};