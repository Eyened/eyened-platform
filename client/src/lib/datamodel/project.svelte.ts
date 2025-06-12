import type { Contact } from "./contact.svelte";
import { BaseItem } from "./itemList";
import { data } from "./model";

export interface ServerProject {
    ProjectID: number,
    ProjectName: string,
    Description?: string,
    ContactID?: number,
}

export class Project extends BaseItem {
    static endpoint = 'projects';
    static mapping = {
        'ProjectName': 'name',
        'Description': 'description',
        'ContactID': 'contact_id',
    };

    id: number = 0;
    name: string = $state('');
    description?: string = $state(undefined);
    contact_id?: number = $state(undefined);

    constructor(item: ServerProject) {
        super();
        this.init(item);
    }

    init(item: ServerProject) {
        this.id = item.ProjectID;
        this.name = item.ProjectName;
        this.description = item.Description;
        this.contact_id = item.ContactID;
    }

    get contact(): Contact | undefined {
        return this.contact_id !== undefined ? data.contacts.get(this.contact_id) : undefined;
    }
}