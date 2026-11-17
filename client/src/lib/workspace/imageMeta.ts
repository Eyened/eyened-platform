import type { ImageGET } from "../../types/openapi_types";
import { eyeRank, modalityRank, type CatalogueEntry } from "./workspaceRules";

export type ImageMeta = Pick<
    ImageGET,
    | "id"
    | "patient"
    | "study"
    | "modality"
    | "etdrs_field"
    | "laterality"
    | "device"
>;

/** A viewport title: the patient ID, never shortened, the rest, which may end in an ellipsis, and the twin number. */
export interface ViewportTitle {
    patient: string;
    rest: string;
    /** "#2", "#3"… for a later image with the same title; empty or missing for the first. */
    twin?: string;
}

/** A viewport's addition to its title, e.g. "· blended with CF F2 · 2017-04-18" and the other image's "#3", kept apart so it never shortens. */
export interface TitleSuffix {
    rest: string;
    twin: string;
}

/** How Layers names an image: a name line over a device line. */
export interface ImageName {
    name: string;
    /** Empty when the manufacturer and model are unknown. */
    device: string;
}

export const MODALITY_LABELS: Partial<Record<string, string>> = {
    ColorFundus: "CF",
    InfraredReflectance: "IR",
    Autofluorescence: "FAF",
    OCT: "OCT",
};

/** "CF F2", "FAF"; null without a modality. */
function modalityField(meta: ImageMeta): string | null {
    const modality = meta.modality
        ? (MODALITY_LABELS[meta.modality] ?? meta.modality)
        : null;
    return modality && meta.etdrs_field
        ? `${modality} ${meta.etdrs_field}`
        : modality;
}

function deviceText(meta: ImageMeta): string {
    return [meta.device.manufacturer, meta.device.model]
        .filter(Boolean)
        .join(" ");
}

export function viewportTitle(meta: ImageMeta): ViewportTitle {
    const eye =
        meta.laterality === "R" ? "OD" : meta.laterality === "L" ? "OS" : null;
    return {
        patient: meta.patient.identifier,
        rest: [eye, modalityField(meta), meta.study.date, deviceText(meta)]
            .filter(Boolean)
            .join(" · "),
    };
}

export function titleText(title: ViewportTitle): string {
    const text = title.rest ? `${title.patient} ${title.rest}` : title.patient;
    return title.twin ? `${text} ${title.twin}` : text;
}

/** "CF F2 · 2017-04-18" and its twin number over "Topcon TRC-NW8"; the public ID when modality and date are unknown. */
export function imageName(meta: ImageMeta, twin: string): ImageName {
    const name =
        [modalityField(meta), meta.study.date].filter(Boolean).join(" · ") ||
        meta.id;
    return { name: twin ? `${name} ${twin}` : name, device: deviceText(meta) };
}

/** Images of one patient with the same title as an earlier image of another instance, numbered "#2", "#3"… in strip order; the rest have no entry. */
export function twinNumbers(
    catalogue: readonly string[],
    metaOf: (imageId: string) => ImageMeta | undefined,
): Map<string, string> {
    const instancesByTitle = new Map<string, string[]>();
    const twins = new Map<string, string>();
    for (const imageId of catalogue) {
        const meta = metaOf(imageId);
        if (!meta) continue;
        const key = `${meta.patient.id} ${viewportTitle(meta).rest}`;
        const ids = instancesByTitle.get(key) ?? [];
        // An OCT volume and its projection share an instance, so they share a number.
        if (!ids.includes(meta.id)) ids.push(meta.id);
        instancesByTitle.set(key, ids);
        const n = ids.indexOf(meta.id) + 1;
        if (n > 1) twins.set(imageId, `#${n}`);
    }
    return twins;
}

export function catalogueEntry(
    imageId: string,
    meta: ImageMeta,
): CatalogueEntry {
    return {
        imageId,
        patient: meta.patient.identifier,
        date: meta.study.date,
        modalityRank: modalityRank(meta.modality, meta.etdrs_field),
        eyeRank: eyeRank(meta.laterality),
    };
}
