import type { JSONSchema } from "$lib/forms/schemaType";
import { BaseItem } from "./baseItem";
import { registerConstructor } from "./model";

export interface ServerFormSchema {
    FormSchemaID: number,
    SchemaName: string,
    Schema: JSONSchema,
}

export class FormSchema extends BaseItem {
    static endpoint = 'form-schemas';
    static mapping = {
        'SchemaName': 'name',
        'Schema': 'schema',
    };

    id!: number;
    name!: string;
    schema: JSONSchema = $state({});

    constructor(serverItem: ServerFormSchema) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerFormSchema) {
        this.id = serverItem.FormSchemaID;
        this.name = serverItem.SchemaName;
        this.schema = serverItem.Schema;
    }
}
registerConstructor('form-schemas', FormSchema);