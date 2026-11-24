import type { ValidationError } from "./formValidator";
import { isRecord, parsePointer } from "./schemaType";

export const MISSING = "Answer this question.";
export const NOT_APPLICABLE =
    "This question doesn't apply any more. Clear the answer.";
export const DONT_FIT = "These answers don't fit together.";

const COMBINATIONS = new Set(["oneOf", "anyOf", "not"]);
// Errors from inside a oneOf/anyOf branch or a not describe alternatives, not what is wrong.
const BRANCH = /\/(oneOf|anyOf)\/\d+\/|\/not\//;

function message(e: ValidationError): string {
    const limit = e.params.limit;
    switch (e.type) {
        case "required":
            return MISSING;
        case "minItems":
            return `Add at least ${limit}.`;
        case "maxItems":
            return `Remove some: up to ${limit}.`;
        case "type": {
            const wanted = String(e.params.type).split(",")[0];
            if (wanted === "integer") return "Enter a whole number.";
            if (wanted === "number") return "Enter a number.";
            return e.message;
        }
        case "enum":
        case "const":
            return "Pick one of the options.";
        case "minimum":
            return `Enter ${limit} or more.`;
        case "maximum":
            return `Enter ${limit} or less.`;
        case "false schema":
            return NOT_APPLICABLE;
        default:
            return e.message;
    }
}

function valueAt(value: unknown, path: string): unknown {
    let current = value;
    for (const key of parsePointer(path)) {
        current =
            typeof current === "object" && current !== null
                ? (current as Record<string, unknown>)[key]
                : undefined;
    }
    return current;
}

/** One message per question path, the first error on a path winning. A oneOf/anyOf/not that fails on a section with nothing to show under it says the answers don't fit together. */
export function fieldErrors(
    errors: readonly ValidationError[],
    value: unknown,
): Map<string, string> {
    const kept = errors.filter(
        (e) =>
            e.type !== "if" &&
            e.type !== "schema" &&
            !BRANCH.test(e.schemaPath),
    );
    const out = new Map<string, string>();
    for (const e of kept) {
        if (!COMBINATIONS.has(e.type) && !out.has(e.path))
            out.set(e.path, message(e));
    }
    for (const e of kept) {
        if (!COMBINATIONS.has(e.type) || out.has(e.path)) continue;
        if (!isRecord(valueAt(value, e.path))) {
            out.set(e.path, e.message);
        } else if (![...out.keys()].some((p) => p.startsWith(`${e.path}/`))) {
            out.set(e.path, DONT_FIT);
        }
    }
    return out;
}
