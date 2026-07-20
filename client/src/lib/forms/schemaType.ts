export type JSONSchemaValue =
    | string
    | number
    | boolean
    | null
    | JSONSchemaValue[]
    | { [key: string]: JSONSchemaValue | undefined }
    | undefined;

export type JSONSchemaType =
    | "string"
    | "number"
    | "integer"
    | "boolean"
    | "object"
    | "array"
    | "null";
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

export function resolveRefs(
    schema: unknown,
    rootSchema: JSONSchema = schema as JSONSchema,
): JSONSchema {
    // Preserve arrays: resolve recursively without converting them into objects
    if (Array.isArray(schema)) {
        return schema.map((item) => resolveRefs(item, rootSchema)) as unknown as JSONSchema;
    }

    if (schema !== null && typeof schema === "object") {
        const schemaRecord = schema as Record<string, unknown>;
        let base: Record<string, unknown> = {};

        // If $ref is present, resolve it first so that local keys override the referenced schema
        const ref = schemaRecord.$ref;
        if (typeof ref === "string") {
            const parts = ref.split("/");
            let refSchema: unknown = rootSchema;
            for (const part of parts.slice(1)) {
                if (part && refSchema !== null && typeof refSchema === "object") {
                    refSchema = (refSchema as Record<string, unknown>)[part];
                }
            }
            base = resolveRefs(refSchema, rootSchema) as unknown as Record<
                string,
                unknown
            >;
        }

        for (const [key, value] of Object.entries(schemaRecord)) {
            if (key === "$ref") continue;
            base[key] = resolveRefs(value, rootSchema);
        }

        return base as JSONSchema;
    }

    return schema as JSONSchema;
}

export function getDefault(schema: JSONSchema) {
    if (schema.type === "object") {
        return {};
    } else if (schema.type === "array") {
        return [];
    } else {
        console.warn("Unknown schema type", schema);
    }
}
