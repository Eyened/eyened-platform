import Ajv, {
    type AnySchema,
    type ErrorObject,
    type ValidateFunction,
} from "ajv";
import Ajv2020 from "ajv/dist/2020";
import { deref, isRecord, pointer, type JSONSchema } from "./schemaType";

export interface ValidationError {
    /** The question's JSON Pointer; a missing answer points at the missing question. */
    path: string;
    /** The ajv keyword, or "schema" when the schema won't compile. */
    type: string;
    params: Record<string, unknown>;
    /** Where in the schema it failed; tells errors inside a oneOf branch apart. */
    schemaPath: string;
    message: string;
}

export interface FormCheck {
    errors: ValidationError[];
    /** Questions a condition rules out for the current answers. */
    ruledOut: Set<string>;
    /** Questions a condition makes required for the current answers. */
    requiredNow: Set<string>;
    /** The schema won't compile, so nothing was checked. */
    schemaError: boolean;
}

// Unknown keys (_order, x-eyened-widget) are ignored, as JSON Schema says; schemas with an $id are not kept by ajv.
const OPTIONS = { strict: false, allErrors: true, addUsedSchema: false };
type Checker = Pick<Ajv, "compile">;
let draft07: Checker | undefined;
let draft2020: Checker | undefined;

/** The build the schema's `$schema` names; 2020-12 when it names none, as the server's jsonschema picks the latest. */
function checkerFor(schema: JSONSchema): Checker {
    if (schema.$schema?.includes("draft-07"))
        return (draft07 ??= new Ajv(OPTIONS));
    return (draft2020 ??= new Ajv2020(OPTIONS));
}

const compiled = new WeakMap<object, ValidateFunction | null>();
const conditions = new WeakMap<object, ValidateFunction | null>();

// ajv resolves "#" against the schema's $id; without one, a ref to the root won't compile when ajv keeps no schemas.
const FORM_ID = "urn:eyened:form";

function compiledFor(schema: JSONSchema): ValidateFunction | null {
    if (!compiled.has(schema)) {
        try {
            compiled.set(
                schema,
                checkerFor(schema).compile({
                    $id: FORM_ID,
                    ...schema,
                } as AnySchema),
            );
        } catch {
            compiled.set(schema, null);
        }
    }
    return compiled.get(schema) ?? null;
}

const SCHEMA_ERROR: ValidationError = {
    path: "",
    type: "schema",
    params: {},
    schemaPath: "",
    message: "The schema won't compile",
};

function toError(e: ErrorObject): ValidationError {
    const path =
        e.keyword === "required"
            ? pointer(e.instancePath, String(e.params.missingProperty))
            : e.instancePath;
    return {
        path,
        type: e.keyword,
        params: e.params,
        schemaPath: e.schemaPath,
        message: e.message ?? e.keyword,
    };
}

/** Whether an `if` holds for these answers; it sees the root's definitions. */
function holds(condition: unknown, value: unknown, root: JSONSchema): boolean {
    if (typeof condition === "boolean") return condition;
    if (!isRecord(condition)) return true;
    if (!conditions.has(condition)) {
        try {
            conditions.set(
                condition,
                checkerFor(root).compile({
                    $id: FORM_ID,
                    ...condition,
                    ...(root.$defs && { $defs: root.$defs }),
                    ...(root.definitions && { definitions: root.definitions }),
                }),
            );
        } catch {
            conditions.set(condition, null);
        }
    }
    const check = conditions.get(condition);
    return check ? check(value) === true : true;
}

/** What the root's own `if` and those in its `allOf` do now: a then/else property set to `false` rules that question out, and its `required` makes questions required. */
function readConditions(
    root: JSONSchema,
    value: unknown,
): Pick<FormCheck, "ruledOut" | "requiredNow"> {
    const ruledOut = new Set<string>();
    const requiredNow = new Set<string>();
    const answers = isRecord(value) ? value : {};
    for (const part of [root, ...(root.allOf ?? [])]) {
        const rule = deref(part, root);
        if (!rule || rule.if === undefined) continue;
        const branch = deref(
            holds(rule.if, answers, root) ? rule.then : rule.else,
            root,
        );
        for (const [key, sub] of Object.entries(branch?.properties ?? {})) {
            if ((sub as unknown) === false) ruledOut.add(pointer("", key));
        }
        for (const key of branch?.required ?? [])
            requiredNow.add(pointer("", key));
    }
    return { ruledOut, requiredNow };
}

/** Every error in the answers; one form-level error when the schema won't compile. */
export function validateSchema(
    schema: JSONSchema,
    value: unknown,
): ValidationError[] {
    const validate = compiledFor(schema);
    if (!validate) return [SCHEMA_ERROR];
    validate(value);
    return (validate.errors ?? []).map(toError);
}

/** The errors, what the conditions do now, and whether the schema compiled. */
export function checkForm(schema: JSONSchema, value: unknown): FormCheck {
    const errors = validateSchema(schema, value);
    if (errors[0] === SCHEMA_ERROR) {
        return {
            errors,
            ruledOut: new Set(),
            requiredNow: new Set(),
            schemaError: true,
        };
    }
    return { errors, ...readConditions(schema, value), schemaError: false };
}
