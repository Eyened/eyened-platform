import { BaseItem, type FilterList } from "./itemList";
import { data } from "./model";
import type { Segmentation } from "./segmentation.svelte";

export interface ServerCreator {
    CreatorID: number;
    CreatorName: string;
    EmployeeIdentifier?: string;
    IsHuman: boolean;
    Description?: string;
    Version?: string;
    Role?: any;
}

export class Creator extends BaseItem {

    static mapping = {
        'EmployeeIdentifier': 'employeeIdentifier',
        'CreatorName': 'name',
        'Description': 'description',
        'IsHuman': 'isHuman',
        'Version': 'version',
        'Role': 'role',
    };
    static endpoint = 'creators';

    id!: number;
    name!: string;
    employeeIdentifier?: string = $state(undefined);
    isHuman!: boolean;
    description?: string = $state(undefined);
    version?: string = $state(undefined);
    role?: number = $state(undefined);

    constructor(item: ServerCreator) {
        super()
        this.init(item);
    }

    init(item: ServerCreator) {
        this.id = item.CreatorID;
        this.name = item.CreatorName;
        this.employeeIdentifier = item.EmployeeIdentifier;
        this.isHuman = item.IsHuman;
        this.description = item.Description;
        this.role = item.Role;
    }

    get segmentations(): FilterList<Segmentation> {
        return data.segmentations.filter(segmentation => segmentation.creatorId == this.id);
    }

    get isAdmin(): boolean {
        if (this.role === undefined) {
            return false;
        }
        return (this.role & 1) === 1;
    }
}