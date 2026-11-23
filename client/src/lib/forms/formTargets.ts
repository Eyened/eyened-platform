import { HIDE_FROM_FORM_PANEL_NAMES } from "$lib/config/builtinFormSchemas";
import {
    getDefault,
    resolveRefs,
    type JSONSchema,
} from "$lib/forms/schemaType";
import { validateSchema } from "$lib/forms/schemaValidator.svelte";
import {
    matchesFormEntityScope,
    resolveFormEntityScope,
    type FormAnnotationContext,
    type FormEntityScope,
} from "$lib/viewer-window/panelForm/formEntityScope";
import {
    deviceText,
    eyeLabel,
    modalityField,
    type ImageMeta,
} from "$lib/workspace/imageMeta";
import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../types/openapi_types";

/** An open image in strip order. */
export interface OpenImage {
    imageId: string;
    instance: ImageMeta;
}

/** The strip's images that have loaded, in strip order. */
export function openImages(
    catalogue: readonly string[],
    images: ReadonlyMap<string, { instance: ImageMeta }>,
): OpenImage[] {
    return catalogue.flatMap((imageId) => {
        const image = images.get(imageId);
        return image ? [{ imageId, instance: image.instance }] : [];
    });
}

/** What one form is about: an image, an eye at a visit, a visit, an eye or the patient. */
export interface FormTarget {
    key: string;
    scope: FormEntityScope;
    /** The row name, e.g. "OD · OCT · 2024-05-02". */
    name: string;
    /** The group header, e.g. "OD · 2024-03-12 (eye at visit)". */
    group: string;
    /** The name with the device, for the tooltip. */
    full: string;
    /** The strip images it covers; an OCT's volume and its projection share one. */
    imageIds: string[];
    ctx: FormAnnotationContext;
    patientId: number;
    /** The patient identifier, for /view's patient headings. */
    patient: string;
}

/** A schema's name; an unnamed schema reads "Form ‹id›". */
export function schemaName(schema: FormSchemaGET): string {
    return schema.name ?? `Form ${schema.id}`;
}

/** The folds that would hide a new form of this target; a create clears them. */
export function foldKeys(target: FormTarget): string[] {
    return ["task", "other", target.key, `patient:${target.patientId}`];
}

const SCOPE_ORDER: readonly FormEntityScope[] = [
    "ImageInstance",
    "StudyEye",
    "Study",
    "Eye",
    "Patient",
];

function describeTarget(
    meta: ImageMeta,
    scope: FormEntityScope,
): Omit<FormTarget, "imageIds"> {
    const patientId = meta.patient.id;
    const laterality = meta.laterality ?? undefined;
    const eye = eyeLabel(meta.laterality);
    const date = meta.study.date;
    const common = { scope, patientId, patient: meta.patient.identifier };
    switch (scope) {
        case "ImageInstance": {
            const name =
                [eye, modalityField(meta), date].filter(Boolean).join(" · ") ||
                meta.id;
            return {
                ...common,
                key: `image:${meta.id}`,
                name,
                group: name,
                full: [name, deviceText(meta)].filter(Boolean).join(" · "),
                ctx: {
                    patientId,
                    studyId: meta.study.id,
                    imageId: meta.id,
                    laterality,
                },
            };
        }
        case "StudyEye": {
            const name = [eye, date].filter(Boolean).join(" · ");
            return {
                ...common,
                key: `studyeye:${patientId}:${meta.study.id}:${laterality ?? ""}`,
                name,
                group: `${name} (eye at visit)`,
                full: name,
                ctx: { patientId, studyId: meta.study.id, laterality },
            };
        }
        case "Study":
            return {
                ...common,
                key: `study:${patientId}:${meta.study.id}`,
                name: date,
                group: `${date} (visit)`,
                full: date,
                ctx: { patientId, studyId: meta.study.id },
            };
        case "Eye": {
            // ASSUMPTION: an image with no laterality gets its own "Eye unknown" target.
            const name = eye ?? "Eye unknown";
            return {
                ...common,
                key: `eye:${patientId}:${laterality ?? ""}`,
                name,
                group: `${name} (eye)`,
                full: name,
                ctx: { patientId, laterality },
            };
        }
        case "Patient":
            return {
                ...common,
                key: `patient:${patientId}`,
                name: "Patient",
                group: "Patient",
                full: "Patient",
                ctx: { patientId },
            };
    }
}

/** The open images grouped into targets of one scope, in strip order. */
export function targetsFor(
    images: readonly OpenImage[],
    scope: FormEntityScope,
): FormTarget[] {
    const targets = new Map<string, FormTarget>();
    for (const { imageId, instance } of images) {
        const described = describeTarget(instance, scope);
        const known = targets.get(described.key);
        if (known) known.imageIds.push(imageId);
        else targets.set(described.key, { ...described, imageIds: [imageId] });
    }
    return [...targets.values()];
}

export interface TaskRow {
    target: FormTarget;
    /** Null until the grader presses Grade. */
    form: FormAnnotationGET | null;
}

export interface FormGroup {
    target: FormTarget;
    /** Newest first. */
    forms: FormAnnotationGET[];
}

export interface Matched {
    taskSchema: FormSchemaGET | null;
    /** One per target of the task schema's scope; null without a task schema or a set. */
    taskRows: TaskRow[] | null;
    /** Every other stored form of an open target, by scope and strip order. */
    other: FormGroup[];
}

const newestFirst = (a: FormAnnotationGET, b: FormAnnotationGET) =>
    b.date_inserted.localeCompare(a.date_inserted) || b.id - a.id;

/** Sorts the stored forms into the task rows and the Other forms groups. */
export function matchForms(input: {
    forms: Iterable<FormAnnotationGET>;
    images: readonly OpenImage[];
    schemas: ReadonlyMap<number, FormSchemaGET>;
    taskSchemaId?: number;
    userId: number;
    subTaskId?: number;
}): Matched {
    const { images, schemas, taskSchemaId, userId, subTaskId } = input;
    const forms = [...input.forms].sort(newestFirst);
    const byScope = new Map<FormEntityScope, FormTarget[]>();
    const targets = (scope: FormEntityScope) => {
        let list = byScope.get(scope);
        if (!list) {
            list = targetsFor(images, scope);
            byScope.set(scope, list);
        }
        return list;
    };

    const taskSchema =
        taskSchemaId === undefined ? null : (schemas.get(taskSchemaId) ?? null);
    // My newest form of the task schema in this set that is about the row's target.
    const taskRows =
        taskSchema && subTaskId !== undefined
            ? targets(resolveFormEntityScope(taskSchema.entity_type)).map(
                  (target) => ({
                      target,
                      form:
                          forms.find(
                              (f) =>
                                  f.form_schema_id === taskSchema.id &&
                                  f.creator.id === userId &&
                                  f.sub_task_id === subTaskId &&
                                  matchesFormEntityScope(
                                      f,
                                      target.scope,
                                      target.ctx,
                                  ),
                          ) ?? null,
                  }),
              )
            : null;

    const inRows = new Set(
        taskRows?.flatMap((row) => (row.form ? [row.form.id] : [])),
    );
    const groups = new Map<string, FormGroup>();
    for (const form of forms) {
        if (inRows.has(form.id)) continue;
        const schema = schemas.get(form.form_schema_id);
        if (!schema || HIDE_FROM_FORM_PANEL_NAMES.has(schemaName(schema)))
            continue;
        const scope = resolveFormEntityScope(schema.entity_type);
        const target = targets(scope).find((t) =>
            matchesFormEntityScope(form, scope, t.ctx),
        );
        if (!target) continue;
        const group = groups.get(target.key) ?? { target, forms: [] };
        group.forms.push(form);
        groups.set(target.key, group);
    }
    const rank = (g: FormGroup) => SCOPE_ORDER.indexOf(g.target.scope);
    const place = (g: FormGroup) => targets(g.target.scope).indexOf(g.target);
    const other = [...groups.values()].sort(
        (a, b) => rank(a) - rank(b) || place(a) - place(b),
    );
    return { taskSchema, taskRows, other };
}

export type Completion = "complete" | "incomplete";

/** Complete when the form window would show no errors: the same value, after resolving refs. */
export function completion(
    form: FormAnnotationGET,
    schema: FormSchemaGET,
): Completion {
    const resolved = resolveRefs(schema.schema as JSONSchema);
    const value = form.form_data || getDefault(resolved);
    return validateSchema(resolved, value).length === 0
        ? "complete"
        : "incomplete";
}

/** Rows with a complete form: the task section's "n of m complete". */
export function completeCount(
    rows: readonly TaskRow[],
    schema: FormSchemaGET,
): number {
    return rows.filter(
        (row) => row.form && completion(row.form, schema) === "complete",
    ).length;
}

/** What "Mark ready" warns about: task rows not graded or not complete, then my other forms in this set that aren't complete. */
export function incompleteForms(
    matched: Matched,
    schemas: ReadonlyMap<number, FormSchemaGET>,
    userId: number,
    subTaskId: number,
): string[] {
    const lines: string[] = [];
    const { taskSchema } = matched;
    for (const { target, form } of matched.taskRows ?? []) {
        if (!taskSchema) break;
        const name = schemaName(taskSchema);
        if (!form) lines.push(`${name} for ${target.name}: not graded`);
        else if (completion(form, taskSchema) === "incomplete")
            lines.push(`${name} for ${target.name}: not complete`);
    }
    for (const { target, forms } of matched.other) {
        for (const form of forms) {
            const schema = schemas.get(form.form_schema_id);
            if (
                schema &&
                form.creator.id === userId &&
                form.sub_task_id === subTaskId &&
                completion(form, schema) === "incomplete"
            )
                lines.push(
                    `${schemaName(schema)} for ${target.name}: not complete`,
                );
        }
    }
    return lines;
}
