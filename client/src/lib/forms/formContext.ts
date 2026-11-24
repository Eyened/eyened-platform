import { getContext, setContext } from "svelte";
import type { JSONSchema } from "./schemaType";

/** What every question of one SchemaForm shares. */
export interface FormContext {
    /** The raw root schema; `$ref`s resolve against it. */
    readonly root: JSONSchema;
    readonly canEdit: boolean;
    /** Radio groups stack their options. */
    readonly vertical: boolean;
    /** The last notice link pressed; sections holding it unfold. */
    readonly reveal: { path: string } | null;
    /** The question's message, once it shows. */
    message(path: string): string | undefined;
    /** Errors show: focus left the question, or a Mark ready attempt was made. */
    shown(path: string): boolean;
    /** A condition rules the question out for the current answers. */
    ruledOut(path: string): boolean;
    /** A condition makes the question required for the current answers. */
    requiredNow(path: string): boolean;
    /** Required questions under a section that have no answer. */
    missing(path: string): number;
    touch(path: string): void;
}

const KEY = Symbol("schemaForm");

export function setFormContext(ctx: FormContext): void {
    setContext(KEY, ctx);
}

export function formContext(): FormContext {
    return getContext<FormContext>(KEY);
}

/** The context key under which ViewerWindow gives the form window "a Mark ready attempt was made in this set". */
export const READY_ATTEMPTED = "markReadyAttempted";

/** What can take focus inside a question, Clear excepted. */
export const FOCUSABLE = 'input:not([type="hidden"]), button:not([data-clear])';

/** What SchemaField hands each field component. */
export interface FieldProps {
    value: unknown;
    onchange: (value: unknown) => void;
    /** The question, with " (required)" when it is. */
    label: string;
    helperText?: string;
    invalidText?: string;
    readonly: boolean;
}
