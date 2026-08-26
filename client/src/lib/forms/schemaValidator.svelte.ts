import { deepEquals } from "./utils";

export class SchemaValidator {
    value: any = $state();
    validation_result = $derived.by(() =>
        run_validation(this.schema, this.value),
    );
    errors = $derived(this.validation_result.errors);
    requiredAbsent = $derived(this.validation_result.absent_keys);
    isValid = $derived(this.errors.length === 0);

    constructor(
        private schema: any,
        value: any,
    ) {
        this.value = value;
    }

    setValue(value: any) {
        this.value = value;
    }

    setProperty(key: string, value: any) {
        if (this.value === undefined) {
            this.value = {};
        }
        this.value[key] = value;
        if (value === undefined) {
            delete this.value[key];
        }
    }

    addArrayValue() {
        if (this.value === undefined) {
            this.value = [];
        }
        this.value.push(undefined);
    }

    setArrayValue(index: number, value: any) {
        if (this.value === undefined) {
            console.warn("Array value is undefined");
            this.value = [];
            return;
        }
        this.value[index] = value;
    }

    removeArrayValue(index: number) {
        if (this.value === undefined) {
            console.warn("Array value is undefined");
            return;
        }
        this.value.splice(index, 1);
    }

    get keysSorted() {
        if (this.schema.properties) {
            const keys_sorted = Object.keys(this.schema.properties);
            if (this.schema._order) {
                keys_sorted.sort(
                    (a, b) =>
                        this.schema._order!.indexOf(a) -
                        this.schema._order!.indexOf(b),
                );
            }
            return keys_sorted;
        }
        return [];
    }

    get inputType() {
        if (this.schema.type === "number" || this.schema.type === "integer") {
            return "number";
        }
        if (this.schema.type === "boolean") {
            return "checkbox";
        }
        return "text";
    }

    get default() {
        return this.schema.default;
    }
}

export interface ValidationError {
    path: string;
    type: string;
    message: string;
}

/** Testable entry point for the recursive JSON Schema checks. */
export function validateSchema(
    schema: unknown,
    value: unknown,
): ValidationError[] {
    return run_validation(schema, value).errors;
}

function run_validation(schema: any, value: any) {
    const absent_keys: string[] = [];
    const errors = validate(schema, value, "", absent_keys);
    return {
        errors,
        absent_keys,
    };
}

function jsonType(value: unknown): string {
    if (value === null) return "null";
    if (Array.isArray(value)) return "array";
    return typeof value;
}

function matchesType(
    schemaType: string | readonly string[],
    value: unknown,
): boolean {
    const allowed = Array.isArray(schemaType) ? schemaType : [schemaType];
    const t = jsonType(value);
    return allowed.some((a) =>
        a === "integer" ? t === "number" && Number.isInteger(value) : a === t,
    );
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validate(
    schema: any,
    value: any,
    path: string = "",
    absent_keys: string[] = [],
): ValidationError[] {
    if (schema === false) {
        return [{ path, type: "", message: "value not allowed" }];
    }
    if (schema === true) {
        return [];
    }
    if (typeof schema !== "object" || schema === null) {
        return [{ path, type: "", message: "invalid schema" }];
    }

    const errors: ValidationError[] = [];
    if (value === undefined) {
        return errors;
    }

    // Type check first so oneOf/{type:"null"} does not match objects, and so
    // we do not recurse into properties of a non-object.
    if (schema.type !== undefined && !matchesType(schema.type, value)) {
        errors.push({
            path,
            type: "type",
            message: `${path || "value"}: Expected ${Array.isArray(schema.type) ? schema.type.join("|") : schema.type}, got ${jsonType(value)}`,
        });
        return errors;
    }

    // Const validation
    if (schema.const !== undefined) {
        if (!deepEquals(value, schema.const)) {
            const message = `${path || "value"}: Value must be ${schema.const}`;
            const error = { path, type: "const", message };
            errors.push(error);
        }
    }

    // Enum validation
    if (schema.enum && Array.isArray(schema.enum)) {
        if (!schema.enum.some((item: any) => deepEquals(value, item))) {
            const message = `${path || "value"}: Invalid value: ${value}`;
            const error = { path, type: "enum", message };
            errors.push(error);
        }
    }

    // Required properties
    if (
        schema.required &&
        Array.isArray(schema.required) &&
        isPlainObject(value)
    ) {
        for (const key of schema.required) {
            if (!(key in value)) {
                const message = `${path}.${key}: Missing required property`;
                const error = {
                    path: `${path}.${key}`,
                    type: "required",
                    message,
                };
                errors.push(error);
            }
        }
    }

    // Object properties validation (recursive)
    if (schema.properties && isPlainObject(value)) {
        for (const key in schema.properties) {
            if (key in value) {
                errors.push(
                    ...validate(
                        schema.properties[key],
                        value[key],
                        `${path}.${key}`,
                        absent_keys,
                    ),
                );
            }
        }
    }

    // additionalProperties: false rejects undeclared keys (e.g. stray `index`
    // on a 2D-only point object). A schema object validates undeclared keys
    // (e.g. pointset registration's per-image PublicID map).
    if (isPlainObject(value)) {
        const declared = new Set(Object.keys(schema.properties ?? {}));
        if (schema.additionalProperties === false) {
            for (const key of Object.keys(value)) {
                if (!declared.has(key)) {
                    errors.push({
                        path: `${path}.${key}`,
                        type: "additionalProperties",
                        message: `${path || "value"}.${key}: Unexpected property`,
                    });
                }
            }
        } else if (
            typeof schema.additionalProperties === "object" &&
            schema.additionalProperties !== null
        ) {
            for (const [key, child] of Object.entries(value)) {
                if (declared.has(key)) continue;
                errors.push(
                    ...validate(
                        schema.additionalProperties,
                        child,
                        `${path}.${key}`,
                        absent_keys,
                    ),
                );
            }
        }
    }

    // Array validation (recursive)
    if (schema.items && Array.isArray(value)) {
        for (const [i, item] of value.entries()) {
            errors.push(
                ...validate(schema.items, item, `${path}[${i}]`, absent_keys),
            );
        }
    }

    // allOf validation (must satisfy all sub-schemas)
    if (schema.allOf && Array.isArray(schema.allOf)) {
        for (const subSchema of schema.allOf) {
            errors.push(...validate(subSchema, value, path, absent_keys));
        }
    }
    // anyOf validation (must satisfy at least one sub-schema)
    if (schema.anyOf && Array.isArray(schema.anyOf)) {
        const anyOfErrors = schema.anyOf.map((subSchema: any) =>
            validate(subSchema, value, path),
        );
        const allFailed = anyOfErrors.every(
            (errList: ValidationError[]) => errList.length > 0,
        );
        if (allFailed) {
            const message = `${path || "value"}: Value does not match any of the required schemas`;
            errors.push({ path, type: "anyOf", message });
        }
    }

    // oneOf validation (must satisfy exactly one sub-schema)
    if (schema.oneOf && Array.isArray(schema.oneOf)) {
        const validSchemas = schema.oneOf.filter(
            (subSchema: any) => validate(subSchema, value, path).length === 0,
        );

        if (validSchemas.length !== 1) {
            const message = `${path || "value"}: Value must match exactly one schema but matched ${validSchemas.length}`;
            errors.push({ path, type: "oneOf", message });
        }
    }

    // not validation (must not satisfy the sub-schema)
    if (schema.not) {
        const notErrors = validate(schema.not, value, path);
        if (notErrors.length === 0) {
            const message = `${path || "value"}: Value should not match the schema`;
            errors.push({ path, type: "not", message });
        }
    }

    // Conditional validation (if-then-else)
    if (schema.if) {
        const ifErrors = validate(schema.if, value, path);
        const subSchema = ifErrors.length === 0 ? schema.then : schema.else;
        const subErrors = validate(subSchema, value, path, absent_keys);
        if (subSchema) {
            let message;

            if (ifErrors.length === 0) {
                message = `If ${formatSatisfies(schema.if)} then ${formatCondition(schema.then, absent_keys)}.`;
            } else {
                message = `If NOT ${formatSatisfies(schema.if)} then ${formatCondition(schema.else, absent_keys)}.`;
            }
            if (subErrors.length > 0) {
                errors.push({ path, type: "if", message });
                errors.push(...subErrors);
            }
        }
    }
    return errors;
}

function formatCondition(
    schema: Record<string, any>,
    absent_keys: string[],
): string {
    const conditions: string[] = [];

    // Handle required fields
    if (schema.required?.length) {
        if (schema.required.length === 1) {
            conditions.push(`'${schema.required[0]}' is required`);
        } else {
            conditions.push(`('${schema.required.join(", ")}') are required`);
        }
    }

    // Handle property conditions
    if (schema.properties && Object.keys(schema.properties).length) {
        const propConditions = Object.entries(schema.properties).map(
            ([key, prop]) => {
                switch (true) {
                    case prop === false:
                        absent_keys.push(key);
                        return `'${key}' should be absent`;
                    case Array.isArray(prop.enum):
                        return `'${key}' in (${prop.enum.map((v: string) => `"${v}"`).join(", ")})`;
                    default:
                        return `'${key}' must satisfy conditions`;
                }
            },
        );

        conditions.push(...propConditions);
    }

    return conditions.length
        ? conditions.join(" and ")
        : "conditions must be met";
}

function formatSatisfies(schema: any): string {
    if (!schema.properties) return "condition";

    const conditions = Object.entries(schema.properties).map(([key, prop]) => {
        if (prop === false) {
            return `'${key}' should be absent`;
        }
        if (Array.isArray(prop.enum)) {
            return `'${key}' in (${prop.enum.map((v: any) => JSON.stringify(v)).join(", ")})`;
        }
        if (prop.const !== undefined) {
            return `'${key}' is ${JSON.stringify(prop.const)}`;
        }
        return `'${key}' meets criteria`;
    });

    return conditions.join(" and ");
}
