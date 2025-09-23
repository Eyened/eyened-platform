import { BaseItem } from "./baseItem";
import { registerConstructor } from "./model";

export interface ServerContact {
    ContactID: number,
    Name: string,
    Email: string,
    Institute: string,
    Orcid: string,
}

export class Contact extends BaseItem {

    static endpoint = 'contacts';
    static mapping = {
        'Name': 'name',
        'Email': 'email',
        'Institute': 'institute',
        'Orcid': 'orcid',
    };

    id!: number;
    name: string = $state('');
    email: string = $state('');
    institute: string = $state('');
    orcid: string = $state('');

    constructor(item: ServerContact) {
        super();
        this.init(item);
    }

    init(serverItem: ServerContact) {
        this.id = serverItem.ContactID;
        this.name = serverItem.Name;
        this.email = serverItem.Email;
        this.institute = serverItem.Institute;
        this.orcid = serverItem.Orcid;
    }
}
registerConstructor('contacts', Contact);