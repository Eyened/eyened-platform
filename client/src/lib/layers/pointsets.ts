import { formAnnotations } from "$lib/data";
import {
    annotationMatchesEye,
    groupKey,
    type EyeLaterality,
} from "$lib/viewer-window/panelRegistration/groupOpenImages";
import type { SyncState } from "$lib/webgl/segmentationState.svelte";
import { MODALITY_LABELS } from "$lib/workspace/imageMeta";
import { SvelteMap } from "svelte/reactivity";
import type { FormAnnotationGET } from "../../types/openapi_types";

/** "patient:eye", the key of one eye's current registration. */
export function eyeKey(instance: {
    patient: { id: number };
    laterality?: string | null;
}): string {
    return groupKey(
        instance.patient.id,
        (instance.laterality ?? null) as EyeLaterality,
    );
}

/** "CF 2024-03-12". */
export function shortImageLabel(instance: {
    modality?: string | null;
    study: { date?: string | null };
}): string {
    const modality = instance.modality
        ? (MODALITY_LABELS[instance.modality] ?? instance.modality)
        : "";
    return [modality, instance.study.date].filter(Boolean).join(" ");
}

/** The point lists in a registration's form data, keyed by public ID. */
function pointLists(formData: unknown): [string, unknown[]][] {
    if (!formData || typeof formData !== "object") return [];
    return Object.entries(formData).filter((e): e is [string, unknown[]] =>
        Array.isArray(e[1]),
    );
}

const placed = (list: unknown[] | undefined, i: number) => list?.[i] != null;

/** Point numbers both images have: the pairs that line them up. */
export function pairCount(formData: unknown, a: string, b: string): number {
    const data = Object.fromEntries(pointLists(formData));
    const length = Math.max(data[a]?.length ?? 0, data[b]?.length ?? 0);
    let pairs = 0;
    for (let i = 0; i < length; i++)
        if (placed(data[a], i) && placed(data[b], i)) pairs++;
    return pairs;
}

export interface RowsWhere {
    schemaId: number;
    /** This image's public ID. */
    instanceId: string;
    patientId: number;
    laterality: EyeLaterality;
    /** The eye's current registration, listed even with no points here. */
    currentId: number | undefined;
    imageLaterality: (imageId: string) => EyeLaterality | undefined;
}

/** This eye's registrations with points on this image, created on it, or current; oldest first, authors mixed. */
export function registrationRows(
    annotations: Iterable<FormAnnotationGET>,
    where: RowsWhere,
): FormAnnotationGET[] {
    const rows: FormAnnotationGET[] = [];
    for (const a of annotations) {
        const eye = annotationMatchesEye(
            a as Parameters<typeof annotationMatchesEye>[0],
            where.schemaId,
            where.patientId,
            where.laterality,
            where.imageLaterality,
        );
        if (!eye) continue;
        const here =
            a.id === where.currentId ||
            a.image_id === where.instanceId ||
            pointLists(a.form_data).some(
                ([id, list]) =>
                    id === where.instanceId && list.some((p) => p != null),
            );
        if (here) rows.push(a);
    }
    return rows.sort((x, y) => x.id - y.id);
}

export type ImageLine = { name: string; points: string; gap: boolean };

/**
 * The current registration's details: this image first, then loaded images in strip order, then the rest by public ID.
 * A gap is a point number other images have and this one lacks. Null when nothing is placed yet.
 */
export function imageLines(
    formData: unknown,
    thisId: string,
    loaded: readonly { id: string; label: string }[],
): ImageLine[] | null {
    const lists = pointLists(formData);
    if (!lists.some(([, list]) => list.some((p) => p != null))) return null;
    const data = Object.fromEntries(lists);
    const length = Math.max(...lists.map(([, list]) => list.length));
    const labels = new Map(loaded.map((image) => [image.id, image.label]));

    const line = (id: string): ImageLine => {
        const label = labels.get(id);
        if (id !== thisId && label === undefined)
            return { name: `${id} (not loaded)`, points: "", gap: false };
        const name = id === thisId ? `This ${label ?? id}` : label!;
        const list = data[id] ?? [];
        const n = list.filter((p) => p != null).length;
        if (n === 0) return { name, points: "no points", gap: false };
        const missing: number[] = [];
        for (let i = 0; i < length; i++) {
            const elsewhere = lists.some(
                ([other, l]) => other !== id && placed(l, i),
            );
            if (!placed(list, i) && elsewhere) missing.push(i + 1);
        }
        return missing.length
            ? { name, points: `${n} · no ${missing.join(", ")}`, gap: true }
            : { name, points: `${n} point${n === 1 ? "" : "s"}`, gap: false };
    };

    const loadedHere = loaded
        .map((image) => image.id)
        .filter((id) => id !== thisId && id in data);
    const unloaded = Object.keys(data)
        .filter((id) => id !== thisId && !labels.has(id))
        .sort();
    return [thisId, ...loadedHere, ...unloaded].map(line);
}

/** The registration a viewport's point tool shows: the eye's current one on a 2D image; editable only while P is armed and it is yours. */
export function pointBinding(input: {
    armed: boolean;
    hidden: boolean;
    is2D: boolean;
    current: FormAnnotationGET | null;
    canEdit: (annotation: FormAnnotationGET) => boolean;
}): { id: number; canEdit: boolean } | null {
    if (input.hidden || !input.is2D || !input.current) return null;
    return {
        id: input.current.id,
        canEdit: input.armed && input.canEdit(input.current),
    };
}

/** Window-wide: each eye's current registration, and each registration's last point save. */
export class PointsetState {
    private readonly currentIds = new SvelteMap<string, number>();
    readonly sync = new SvelteMap<number, SyncState>();

    currentId(eye: string): number | undefined {
        return this.currentIds.get(eye);
    }

    /** The eye's current registration; null when unset or deleted. */
    current(eye: string): FormAnnotationGET | null {
        const id = this.currentIds.get(eye);
        return id === undefined ? null : (formAnnotations.get(id) ?? null);
    }

    setCurrent(eye: string, id: number | undefined): void {
        if (id === undefined) this.currentIds.delete(eye);
        else this.currentIds.set(eye, id);
    }
}
