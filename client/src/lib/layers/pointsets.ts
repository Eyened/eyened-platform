import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import { formAnnotations, formSchemasByName, instances } from "$lib/data";
import {
    annotationMatchesEye,
    groupKey,
    type EyeLaterality,
} from "$lib/viewer-window/panelRegistration/groupOpenImages";
import type { SyncState } from "$lib/webgl/segmentationState.svelte";
import {
    imageName,
    type ImageMeta,
    type ImageName,
} from "$lib/workspace/imageMeta";
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

/** " · OD" for a right eye, " · OS" for a left one, nothing when the eye is unknown. */
export function eyeSuffix(laterality: string | null | undefined): string {
    return laterality === "R" ? " · OD" : laterality === "L" ? " · OS" : "";
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

/** The registration form schema's id; undefined until the schemas load. */
export function registrationSchemaId(): number | undefined {
    return formSchemasByName.get(
        BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION,
    )?.id;
}

/** The image's eye's registrations to list, reading the stores; none while the registration schema is missing. */
export function eyeRegistrationRows(
    instance: {
        id: string;
        patient: { id: number };
        laterality?: string | null;
    },
    inUseId: number | undefined,
): FormAnnotationGET[] {
    const schemaId = registrationSchemaId();
    return schemaId === undefined
        ? []
        : registrationRows(formAnnotations.values(), {
              schemaId,
              instanceId: instance.id,
              patientId: instance.patient.id,
              laterality: (instance.laterality ?? null) as EyeLaterality,
              currentId: inUseId,
              imageLaterality: (id) =>
                  (instances.get(id)?.laterality ?? null) as EyeLaterality,
          });
}

/** This eye's loaded 2D images, in strip order. */
export function loadedEyeImages(
    catalogue: readonly string[],
    win: {
        images: ReadonlyMap<string, { is2D: boolean; instance: ImageMeta }>;
        twins: ReadonlyMap<string, string>;
    },
    eye: string,
): ({ id: string } & ImageName)[] {
    return catalogue.flatMap((imageId) => {
        const image = win.images.get(imageId);
        return image?.is2D && eyeKey(image.instance) === eye
            ? [
                  {
                      id: image.instance.id,
                      ...imageName(
                          image.instance,
                          win.twins.get(imageId) ?? "",
                      ),
                  },
              ]
            : [];
    });
}

export type ImageLine = {
    name: string;
    device: string;
    points: string;
    gap: boolean;
};

/**
 * The current registration's details: this image first, then loaded images in strip order, then the rest by public ID.
 * A gap is a point number other images have and this one lacks. Null when nothing is placed yet.
 */
export function imageLines(
    formData: unknown,
    thisId: string,
    loaded: readonly ({ id: string } & ImageName)[],
): ImageLine[] | null {
    const lists = pointLists(formData);
    if (!lists.some(([, list]) => list.some((p) => p != null))) return null;
    const data = Object.fromEntries(lists);
    const length = Math.max(...lists.map(([, list]) => list.length));
    const names = new Map(loaded.map((image) => [image.id, image]));

    const line = (id: string): ImageLine => {
        const image = names.get(id);
        if (id !== thisId && image === undefined)
            return {
                name: `${id} (not loaded)`,
                device: "",
                points: "",
                gap: false,
            };
        const name = id === thisId ? `This ${image?.name ?? id}` : image!.name;
        const device = image?.device ?? "";
        const list = data[id] ?? [];
        const n = list.filter((p) => p != null).length;
        if (n === 0) return { name, device, points: "no points", gap: false };
        const missing: number[] = [];
        for (let i = 0; i < length; i++) {
            const elsewhere = lists.some(
                ([other, l]) => other !== id && placed(l, i),
            );
            if (!placed(list, i) && elsewhere) missing.push(i + 1);
        }
        return missing.length
            ? {
                  name,
                  device,
                  points: `${n} · no ${missing.join(", ")}`,
                  gap: true,
              }
            : {
                  name,
                  device,
                  points: `${n} point${n === 1 ? "" : "s"}`,
                  gap: false,
              };
    };

    const loadedHere = loaded
        .map((image) => image.id)
        .filter((id) => id !== thisId && id in data);
    const unloaded = Object.keys(data)
        .filter((id) => id !== thisId && !names.has(id))
        .sort();
    return [thisId, ...loadedHere, ...unloaded].map(line);
}

/** What P binds in a viewport. */
export interface PointTarget {
    /** The registration this viewport shows and P binds; null when none. */
    id: number | null;
    /** P may move its points. */
    canEdit: boolean;
    /** Why P can't place here; null when it can, or when P does not apply. */
    reason: string | null;
}

/** P binds the selected pointset while armed; otherwise the viewport shows the eye's registration in use, read-only. */
export function pointBinding(input: {
    armed: boolean;
    hidden: boolean;
    is2D: boolean;
    selected: FormAnnotationGET | null;
    inUse: FormAnnotationGET | null;
    canEdit: (annotation: FormAnnotationGET) => boolean;
}): PointTarget {
    if (input.hidden || !input.is2D)
        return { id: null, canEdit: false, reason: null };
    const editing = input.armed ? input.selected : null;
    return {
        id: (editing ?? input.inUse)?.id ?? null,
        canEdit: editing !== null && input.canEdit(editing),
        reason: input.selected ? null : "Select a pointset to add points",
    };
}

/** Window-wide: each eye's registration in use (Display › Registration), and each registration's last point save. */
export class PointsetState {
    private readonly currentIds = new SvelteMap<string, number>();
    readonly sync = new SvelteMap<number, SyncState>();

    /** The id of the eye's registration in use; undefined when unset or deleted. */
    currentId(eye: string): number | undefined {
        const id = this.currentIds.get(eye);
        return id !== undefined && formAnnotations.has(id) ? id : undefined;
    }

    /** The eye's registration in use; null when unset or deleted. */
    current(eye: string): FormAnnotationGET | null {
        const id = this.currentIds.get(eye);
        return id === undefined ? null : (formAnnotations.get(id) ?? null);
    }

    setCurrent(eye: string, id: number | undefined): void {
        if (id === undefined) this.currentIds.delete(eye);
        else this.currentIds.set(eye, id);
    }
}
