import { BaseItem } from "./baseItem";
import { registerConstructor } from "./model";

export interface ServerScan {
    ScanID: number,
    ScanMode: string,
}

export class Scan extends BaseItem {
    static endpoint = 'scans';
    static mapping = {
        'ScanMode': 'mode',
    };

    id!: number;
    mode!: string;

    constructor(item: ServerScan) {
        super();
        this.init(item);
    }

    init(item: ServerScan) {
        this.id = item.ScanID;
        this.mode = item.ScanMode;
    }
}
registerConstructor('scans', Scan);