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

/** An OCT shown as two images: its en-face projection (`<id>_proj`) and its B-scans. */
export type OctPart = "enface" | "bscans";

/** A viewport title. The patient ID with sex and age, and the eye, never shorten; the rest may end in an ellipsis; then the twin number. */
export interface ViewportTitle {
    patient: string;
    /** "F · 72 y"; empty or missing when sex and age are unknown. */
    demographics?: string;
    /** "female, 72 years": the title's accessible description. */
    demographicsText?: string;
    /** "OD", "OS"; empty or missing when the eye is unknown. */
    eye?: string;
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

const OCT_WORDS: Record<OctPart, string> = {
    enface: "OCT en-face",
    bscans: "OCT B-scans",
};

/** "CF F2", "FAF", "OCT en-face"; null without a modality. */
export function modalityField(meta: ImageMeta, oct?: OctPart): string | null {
    if (oct) return OCT_WORDS[oct];
    const modality = meta.modality
        ? (MODALITY_LABELS[meta.modality] ?? meta.modality)
        : null;
    return modality && meta.etdrs_field
        ? `${modality} ${meta.etdrs_field}`
        : modality;
}

export function deviceText(meta: ImageMeta): string {
    return [meta.device.manufacturer, meta.device.model]
        .filter(Boolean)
        .join(" ");
}

/** "OD", "OS"; null when the eye is unknown. */
export function eyeLabel(
    laterality: ImageMeta["laterality"],
): "OD" | "OS" | null {
    return laterality === "R" ? "OD" : laterality === "L" ? "OS" : null;
}

/** "enface" for an OCT's projection, "bscans" for a volume whose projection is open; undefined for any other image. */
export function octPart(
    imageId: string,
    isOpen: (imageId: string) => boolean,
): OctPart | undefined {
    if (imageId.endsWith("_proj")) return "enface";
    return isOpen(`${imageId}_proj`) ? "bscans" : undefined;
}

/** Whole years from a birth date to a visit date, both read as "YYYY-MM-DD" text so no time zone moves a day; null when either is missing or the birth is after the visit. */
export function ageAt(
    birthDate: string | null | undefined,
    visitDate: string | null | undefined,
): number | null {
    const birth = dateParts(birthDate);
    const visit = dateParts(visitDate);
    if (!birth || !visit) return null;
    const [by, bm, bd] = birth;
    const [vy, vm, vd] = visit;
    const age = vy - by - (vm < bm || (vm === bm && vd < bd) ? 1 : 0);
    return age < 0 ? null : age;
}

// The server sends dates as "YYYY-MM-DD".
function dateParts(
    date: string | null | undefined,
): [number, number, number] | null {
    return date
        ? (date.split("-").map(Number) as [number, number, number])
        : null;
}

const SEX_WORDS = { F: "female", M: "male" } as const;

function demographics(
    meta: ImageMeta,
): Pick<ViewportTitle, "demographics" | "demographicsText"> {
    const sex = meta.patient.sex ?? null;
    const age = ageAt(meta.patient.birth_date, meta.study.date);
    return {
        demographics: [sex, age === null ? null : `${age} y`]
            .filter(Boolean)
            .join(" · "),
        demographicsText: [
            sex ? SEX_WORDS[sex] : null,
            age === null ? null : `${age} ${age === 1 ? "year" : "years"}`,
        ]
            .filter(Boolean)
            .join(", "),
    };
}

export function viewportTitle(
    meta: ImageMeta,
    { oct }: { oct?: OctPart } = {},
): ViewportTitle {
    return {
        patient: meta.patient.identifier,
        ...demographics(meta),
        eye: eyeLabel(meta.laterality) ?? "",
        rest: [modalityField(meta, oct), meta.study.date, deviceText(meta)]
            .filter(Boolean)
            .join(" · "),
    };
}

export function titleText(title: ViewportTitle): string {
    const head = title.demographics
        ? `${title.patient} · ${title.demographics}`
        : title.patient;
    const body = [title.eye, title.rest].filter(Boolean).join(" · ");
    const text = body ? `${head} ${body}` : head;
    return title.twin ? `${text} ${title.twin}` : text;
}

/** "CF F2 · 2017-04-18" and its twin number over "Topcon TRC-NW8"; the public ID when modality and date are unknown. */
export function imageName(
    meta: ImageMeta,
    twin: string,
    oct?: OctPart,
): ImageName {
    const name =
        [modalityField(meta, oct), meta.study.date]
            .filter(Boolean)
            .join(" · ") || meta.id;
    return { name: twin ? `${name} ${twin}` : name, device: deviceText(meta) };
}

/** An Images row's name line: "OD · CF F2", "OD · OCT en-face"; the public ID when eye and modality are unknown. */
export function imageRowName(meta: ImageMeta, oct?: OctPart): string {
    return (
        [eyeLabel(meta.laterality), modalityField(meta, oct)]
            .filter(Boolean)
            .join(" · ") || meta.id
    );
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
        // Without the OCT part, so an en-face and its volume share a number.
        const { eye, rest } = viewportTitle(meta);
        const key = `${meta.patient.id} ${eye} ${rest}`;
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
