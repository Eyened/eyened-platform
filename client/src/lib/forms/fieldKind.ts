import { isPointWidget } from "./pointSchema";
import { deref, parsePointer, type JSONSchema } from "./schemaType";

export type FieldKind =
    | "radios"
    | "dropdown"
    | "yesno"
    | "checkboxes"
    | "multiselect"
    | "number"
    | "text"
    | "section"
    | "group-list"
    | "value-list"
    | "point"
    | "unsupported";

/** Up to this many options show as radios or checkboxes; more go in a list (Carbon Forms: more than five, use a select list). */
const MAX_VISIBLE_OPTIONS = 5;

const VALUE_TYPES = ["string", "number", "integer"];

/** The type a field stores: a type array's first non-null entry. */
export function storedType(schema: JSONSchema): string | undefined {
    const type = schema.type;
    if (!Array.isArray(type)) return type as string | undefined;
    return type.find((t) => t !== "null");
}

/** The question's words: title, else description (what real schemas use), else the key. */
export function questionTitle(
    schema: JSONSchema | undefined,
    fallback: string,
): string {
    return schema?.title ?? schema?.description ?? fallback;
}

/** Property keys in `_order` order; keys it doesn't list keep their place after it. */
export function orderedKeys(schema: JSONSchema): string[] {
    const order = schema._order ?? [];
    const rank = (key: string) => {
        const i = order.indexOf(key);
        return i < 0 ? order.length : i;
    };
    return Object.keys(schema.properties ?? {}).sort(
        (a, b) => rank(a) - rank(b),
    );
}

/** How a question is drawn; `schema` is already deref'd, `root` resolves its list items. */
export function fieldKind(schema: JSONSchema, root: JSONSchema): FieldKind {
    if (isPointWidget(schema)) return "point";
    const type = storedType(schema);
    if (
        Array.isArray(schema.enum) &&
        (type === undefined || VALUE_TYPES.includes(type))
    ) {
        return schema.enum.length <= MAX_VISIBLE_OPTIONS
            ? "radios"
            : "dropdown";
    }
    switch (type) {
        case "boolean":
            return "yesno";
        case "number":
        case "integer":
            return "number";
        case "string":
            return "text";
        case "object":
            return schema.properties ? "section" : "unsupported";
        case "array": {
            const items = deref(schema.items, root);
            if (!items) return "unsupported";
            if (Array.isArray(items.enum)) {
                return items.enum.length <= MAX_VISIBLE_OPTIONS
                    ? "checkboxes"
                    : "multiselect";
            }
            const itemType = storedType(items);
            if (itemType === "object" && items.properties) return "group-list";
            if (itemType && VALUE_TYPES.includes(itemType)) return "value-list";
            return "unsupported";
        }
        default:
            return "unsupported";
    }
}

/** The words for the question at `path`; an entry of a list is "‹item› n". */
export function titleAt(root: JSONSchema, path: string): string {
    let node = deref(root, root);
    let title = "This form";
    for (const key of parsePointer(path)) {
        if (!node) break;
        if (storedType(node) === "array") {
            const items = deref(node.items, root);
            title = `${questionTitle(items, "Entry")} ${Number(key) + 1}`;
            node = items;
        } else {
            node = deref(node.properties?.[key], root);
            title = questionTitle(node, key);
        }
    }
    return title;
}
