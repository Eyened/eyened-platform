import type { JSONSchema } from "$lib/forms/schemaType";
import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";

export interface FormSchema extends Item {
    id: number,
    name: string,
    schema: JSONSchema,
}

export const FormSchemaConstructor = new ItemConstructor<FormSchema>(
    'FormSchemaID', {
    name: 'SchemaName',
    schema: 'Schema',
});
