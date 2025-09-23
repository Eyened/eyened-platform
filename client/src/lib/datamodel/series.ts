import type { Instance } from "./instance.svelte";
import { BaseItem } from "./baseItem";
import { FilterList } from "./itemList";
import { data, registerConstructor } from "./model";
import type { Study } from "./study";

export interface ServerSeries {
    SeriesID: number;
    StudyID: number;
    SeriesDescription: string;
    SeriesNumber: number;
    SeriesInstanceUID: string;
}

export class Series extends BaseItem {
    static endpoint = 'series';
    static mapping = {
        'StudyID': 'studyId',
        'SeriesDescription': 'description',
        'SeriesNumber': 'number',
        'SeriesInstanceUID': 'instanceUID',
    };

    id!: number;
    studyId!: number;
    description!: string;
    number!: number;
    instanceUID!: string;

    constructor(item: ServerSeries) {
        super();
        this.init(item);
    }

    init(item: ServerSeries) {
        this.id = item.SeriesID;
        this.studyId = item.StudyID;
        this.description = item.SeriesDescription;
        this.number = item.SeriesNumber;
        this.instanceUID = item.SeriesInstanceUID;
    }

    get instances(): FilterList<Instance> {
        return data.instances.filter(instance => instance.seriesId == this.id);
    }

    get study(): Study {
        return data.studies.get(this.studyId)!;
    }
}
registerConstructor('series', Series);