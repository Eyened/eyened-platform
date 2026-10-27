/** One operator of a property; `value` picks the value editor ("none": no value part). */
export type BuilderOperator = {
    id: string;
    label: string;
    value: "list" | "text" | "number" | "date" | "none";
    /** Shown under the text field, e.g. how to enter several values. */
    helperText?: string;
};

/** A property (a search field) with its operators and, for a list, its values. */
export type BuilderProperty = {
    id: string;
    label: string;
    operators: BuilderOperator[];
    options: string[];
};

/**
 * One condition. Its parts appear in order: property, then operator, then value.
 * `incomplete`: its first missing part was closed without a choice ("Incomplete").
 */
export type BuilderRow = {
    id: number;
    property?: string;
    operator?: string;
    value?: string | string[];
    incomplete?: boolean;
};
