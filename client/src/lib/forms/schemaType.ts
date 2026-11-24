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
    enum?: readonly unknown[];
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
    additionalProperties?: boolean | JSONSchema;
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
    $defs?: Readonly<Record<string, JSONSchema>>;
    title?: string | undefined;
    description?: string | undefined;
    default?: unknown;
    readOnly?: boolean | undefined;
    writeOnly?: boolean | undefined;
    examples?: readonly unknown[];
    nullable?: boolean;
    _order?: readonly string[];
    /** Eyened UI widget hint (ignored by jsonschema validators). */
    "x-eyened-widget"?: "keypoint" | (string & {});
};

export function getDefault(schema: JSONSchema) {
    if (schema.type === "object") {
        return {};
    } else if (schema.type === "array") {
        return [];
    } else {
        console.warn("Unknown schema type", schema);
    }
}

/** A plain object: not null and not an array. */
export function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** The keys of a JSON Pointer such as "/naevi/0/size", unescaped. */
export function parsePointer(path: string): string[] {
    if (path === "") return [];
    return path
        .split("/")
        .slice(1)
        .map((part) => part.replace(/~1/g, "/").replace(/~0/g, "~"));
}

/** The JSON Pointer to `key` under `parent`, written as ajv writes instancePath. */
export function pointer(parent: string, key: string | number): string {
    return `${parent}/${String(key).replace(/~/g, "~0").replace(/\//g, "~1")}`;
}

/** The schema `node` stands for: a local `$ref` followed (keys next to it win), or undefined when it is missing. */
export function deref(node: unknown, root: JSONSchema): JSONSchema | undefined {
    let current = node;
    while (isRecord(current) && typeof current.$ref === "string") {
        const ref = current.$ref;
        if (!ref.startsWith("#")) return undefined;
        let target: unknown = root;
        for (const key of parsePointer(ref.slice(1))) {
            target = isRecord(target) ? target[key] : undefined;
        }
        if (!isRecord(target)) return undefined;
        const rest = { ...current };
        delete rest.$ref;
        current = { ...target, ...rest };
    }
    return isRecord(current) ? (current as JSONSchema) : undefined;
}
