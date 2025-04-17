export type JSONSchemaType = "string" | "number" | "integer" | "boolean" | "object" | "array" | "null";
export type JSONSchema = {
    $id?: string | undefined;
    $ref?: string | undefined;
    $schema?: string | undefined;
    $comment?: string | undefined;
    type?: JSONSchemaType | readonly JSONSchemaType[];
    const?: unknown;
    enum?: readonly JSONSchemaType[];
    multipleOf?: number | undefined;
    maximum?: number | undefined;
    exclusiveMaximum?: number | undefined;
    minimum?: number | undefined;
    exclusiveMinimum?: number | undefined;
    maxLength?: number | undefined;
    minLength?: number | undefined;
    pattern?: string | undefined;
    items?: JSONSchema;
    additionalItems?: JSONSchema;
    contains?: JSONSchema;
    maxItems?: number | undefined;
    minItems?: number | undefined;
    uniqueItems?: boolean | undefined;
    maxProperties?: number | undefined;
    minProperties?: number | undefined;
    required?: readonly string[];
    properties?: Readonly<Record<string, JSONSchema>>;
    patternProperties?: Readonly<Record<string, JSONSchema>>;
    additionalProperties?: JSONSchema;
    unevaluatedProperties?: JSONSchema;
    dependencies?: Readonly<Record<string, JSONSchema | readonly string[]>>;
    propertyNames?: JSONSchema;
    if?: JSONSchema;
    then?: JSONSchema;
    else?: JSONSchema;
    allOf?: readonly JSONSchema[];
    anyOf?: readonly JSONSchema[];
    oneOf?: readonly JSONSchema[];
    not?: JSONSchema;
    format?: string | undefined;
    contentMediaType?: string | undefined;
    contentEncoding?: string | undefined;
    definitions?: Readonly<Record<string, JSONSchema>>;
    title?: string | undefined;
    description?: string | undefined;
    default?: unknown;
    readOnly?: boolean | undefined;
    writeOnly?: boolean | undefined;
    examples?: readonly unknown[];
    nullable?: boolean;
    _order?: readonly string[];
};

export function resolveRefs(schema: JSONSchema, rootSchema: JSONSchema = schema): JSONSchema {
    if (typeof schema === 'object') {
        for (const [key, value] of Object.entries(schema)) {
            if (key === '$ref') {
                // Assuming the ref is a JSON Pointer with root reference
                const refParts = value.split('/');
                let refSchema: any = rootSchema;
                for (const part of refParts.slice(1)) {
                    refSchema = refSchema[part];
                }
                schema = { ...schema, ...resolveRefs(refSchema, rootSchema) };
                delete schema['$ref'];
            } else {
                schema[key] = resolveRefs(value as JSONSchema, rootSchema);
            }
        }
    }
    return schema;
}

export function getDefault(schema: JSONSchema) {
    if (schema.type === 'object') {
        return {};
    } else if (schema.type === 'array') {
        return [];
    } else {
        console.warn('Unknown schema type', schema);
    }
}