import type {
    BuilderOperator,
    BuilderProperty,
    BuilderRow,
} from "$lib/components/ui/condition-builder/types.js";
import { parseDate } from "@internationalized/date";
import type {
    SearchCondition,
    SignatureField,
} from "../../types/openapi_types";

// The condition builder's operators per search field (ConditionBuilder's labels), and the mapping
// between builder rows and the search API's conditions. Used by the builder and by BrowserContext.

type ServerOperator = SearchCondition["operator"];
type Operator = BuilderOperator & { server: ServerOperator };

function op(
    id: string,
    label: string,
    server: ServerOperator,
    value: BuilderOperator["value"],
    helperText?: string,
): Operator {
    return helperText
        ? { id, label, server, value, helperText }
        : { id, label, server, value };
}

/** A signature field's operators, in menu order. */
export function operatorsFor(field: SignatureField): Operator[] {
    const ops: Operator[] = [];
    if (Array.isArray(field.values)) {
        ops.push(op("oneOf", "is one of", "IN", "list"));
    } else if (field.values === "int" || field.values === "float") {
        ops.push(
            op("is", "is", "==", "number"),
            op("greater", "is greater than", ">", "number"),
            op("lower", "is lower than", "<", "number"),
        );
    } else if (field.values === "date") {
        ops.push(
            op("is", "is", "==", "date"),
            op("before", "is before", "<", "date"),
            op("after", "is after", ">", "date"),
        );
    } else {
        // "string", and any type the server adds later: free text, as v1.
        ops.push(op("is", "is", "==", "text"));
        if (field.values === "string" && field.multi) {
            // v1: several values in one field, comma-separated.
            ops.push(
                op(
                    "oneOf",
                    "is one of",
                    "IN",
                    "text",
                    "Separate values with commas",
                ),
            );
        }
    }
    if (field.nullable) ops.push(op("isEmpty", "is empty", "IS NULL", "none"));
    return ops;
}

/** v1's encoding: an attribute is model__feature__name ("none" without a feature). */
function propertyId(field: SignatureField): string {
    return field.type === "attribute"
        ? `${field.model ?? ""}__${field.feature ?? "none"}__${field.name}`
        : field.name;
}

function propertyLabel(field: SignatureField): string {
    if (field.type !== "attribute") return field.name;
    return field.feature
        ? `${field.name} (${field.model}, ${field.feature})`
        : `${field.name} (${field.model})`;
}

function fieldById(signature: SignatureField[], id: string) {
    return signature.find((f) => propertyId(f) === id);
}

export function builderProperties(
    signature: SignatureField[],
): BuilderProperty[] {
    return signature.map((field) => ({
        id: propertyId(field),
        label: propertyLabel(field),
        operators: operatorsFor(field),
        options: Array.isArray(field.values) ? field.values : [],
    }));
}

export function labelFor(id: string, signature: SignatureField[]): string {
    const field = fieldById(signature, id);
    return field ? propertyLabel(field) : id;
}

export function isIsoDate(text: string): boolean {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return false;
    try {
        parseDate(text);
        return true;
    } catch {
        return false;
    }
}

/** The condition value for a row's value, or undefined while it is incomplete. */
function conditionValue(
    operator: Operator,
    raw: BuilderRow["value"],
): SearchCondition["value"] | undefined {
    if (operator.value === "none") return null;
    if (operator.value === "list") {
        return Array.isArray(raw) && raw.length > 0 ? [...raw] : undefined;
    }
    const text = typeof raw === "string" ? raw.trim() : "";
    if (text === "") return undefined;
    if (operator.value === "number") {
        const n = Number(text);
        return Number.isFinite(n) ? n : undefined;
    }
    if (operator.value === "date") return isIsoDate(text) ? text : undefined;
    if (operator.server === "IN") {
        const parts = text
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        return parts.length > 0 ? parts : undefined;
    }
    return text;
}

/** The search conditions of the complete rows; incomplete rows are left out. */
export function rowsToConditions(
    rows: BuilderRow[],
    signature: SignatureField[],
): SearchCondition[] {
    return rows.flatMap((row) => {
        const field = row.property
            ? fieldById(signature, row.property)
            : undefined;
        const operator =
            field && operatorsFor(field).find((o) => o.id === row.operator);
        if (!field || !operator) return [];
        const value = conditionValue(operator, row.value);
        if (value === undefined) return [];
        const condition = {
            variable: field.name,
            operator: operator.server,
            value,
        };
        return [
            (field.type === "attribute"
                ? {
                      type: "attribute",
                      model: field.model ?? "",
                      feature: field.feature ?? undefined,
                      ...condition,
                  }
                : { type: "default", ...condition }) as SearchCondition,
        ];
    });
}

function rowValue(
    operator: Operator,
    value: SearchCondition["value"],
): BuilderRow["value"] {
    if (operator.value === "none") return undefined;
    const list = Array.isArray(value)
        ? value.map(String)
        : value == null
          ? []
          : [String(value)];
    return operator.value === "list" ? list : list.join(", ");
}

/** Builder rows for conditions (a URL, the picker's seed); conditions the signature cannot show are dropped. */
export function conditionsToRows(
    conditions: SearchCondition[],
    signature: SignatureField[],
): BuilderRow[] {
    const rows: BuilderRow[] = [];
    for (const c of conditions) {
        const field = signature.find(
            (f) =>
                f.name === c.variable &&
                (c.type === "attribute"
                    ? f.type === "attribute" &&
                      f.model === (c.model ?? "") &&
                      (f.feature ?? null) === (c.feature ?? null)
                    : f.type !== "attribute"),
        );
        const operator =
            field && operatorsFor(field).find((o) => o.server === c.operator);
        if (!field || !operator) continue;
        rows.push({
            id: rows.length + 1,
            property: propertyId(field),
            operator: operator.id,
            value: rowValue(operator, c.value),
        });
    }
    return rows;
}

/** Whether a row still applies with this signature (the Studies/Images switch keeps only these). */
export function acceptsRow(
    row: BuilderRow,
    signature: SignatureField[],
): boolean {
    if (!row.property) return true;
    const field = fieldById(signature, row.property);
    return (
        !!field &&
        (!row.operator ||
            operatorsFor(field).some((o) => o.id === row.operator))
    );
}
