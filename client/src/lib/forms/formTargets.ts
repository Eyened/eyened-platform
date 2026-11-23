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
    /** The patient identifier, for the patient headings and texts. */
    patient: string;
}

/** A schema's name; an unnamed schema reads "Form ‹id›". */
export function schemaName(schema: FormSchemaGET): string {
    return schema.name ?? `Form ${schema.id}`;
}

/** The folds that would hide a new form of this target; a create clears them. */
export function foldKeys(target: FormTarget): string[] {
    const id = target.patientId;
    return [
        "task",
        "other",
        target.key,
        `patient:${id}`,
        `task:patient:${id}`,
        `other:patient:${id}`,
    ];
}

/** The target as the status messages and "isn't complete" lines name it: with the patient when several are open. */
export function targetText(target: FormTarget, multiPatient: boolean): string {
    return multiPatient ? `${target.patient} · ${target.name}` : target.name;
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
    /** The open images belong to more than one patient. */
    multiPatient: boolean;
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
    const multiPatient =
        new Set(images.map((i) => i.instance.patient.id)).size > 1;
    return { taskSchema, taskRows, other, multiPatient };
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
    const { taskSchema, multiPatient } = matched;
    for (const { target, form } of matched.taskRows ?? []) {
        if (!taskSchema) break;
        const name = schemaName(taskSchema);
        if (!form)
            lines.push(
                `${name} for ${targetText(target, multiPatient)}: not graded`,
            );
        else if (completion(form, taskSchema) === "incomplete")
            lines.push(
                `${name} for ${targetText(target, multiPatient)}: not complete`,
            );
    }
    for (const { target, forms } of matched.other) {
        for (const form of forms) {
            const schema = schemas.get(form.form_schema_id);
            // My other forms of the task schema in this set are superseded by the row's newest one.
            if (
                schema &&
                form.creator.id === userId &&
                form.sub_task_id === subTaskId &&
                form.form_schema_id !== taskSchema?.id &&
                completion(form, schema) === "incomplete"
            )
                lines.push(
                    `${schemaName(schema)} for ${targetText(target, multiPatient)}: not complete`,
                );
        }
    }
    return lines;
}

/** What a form is about, under the form window's heading. */
export const ABOUT: Record<FormEntityScope, string> = {
    ImageInstance: "about this image",
    StudyEye: "about this eye at this visit",
    Study: "about this visit",
    Eye: "about this eye",
    Patient: "about this patient",
};

/** The form window's heading: the target in the viewport title's words, e.g. "P-0042 · OD · OCT · 2024-03-12" or "P-0042 · OD · visit 2024-03-12". */
export function windowHeading(
    scope: FormEntityScope,
    parts: {
        patient: string;
        eye: string | null;
        modality: string | null;
        date: string | null;
    },
): string {
    const { patient, eye, modality, date } = parts;
    const visit = date ? `visit ${date}` : null;
    const rest =
        scope === "ImageInstance"
            ? [eye, modality, date]
            : scope === "StudyEye"
              ? [eye, visit]
              : scope === "Study"
                ? [visit]
                : scope === "Eye"
                  ? [eye]
                  : [];
    return [patient, ...rest].filter(Boolean).join(" · ");
}

/** The open target a stored form is about, or null when none of its images is open. */
export function targetOf(
    form: FormAnnotationGET,
    schema: FormSchemaGET,
    images: readonly OpenImage[],
): FormTarget | null {
    const scope = resolveFormEntityScope(schema.entity_type);
    return (
        targetsFor(images, scope).find((t) =>
            matchesFormEntityScope(form, scope, t.ctx),
        ) ?? null
    );
}
