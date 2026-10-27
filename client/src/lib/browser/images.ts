import { instances } from "$lib/data/stores.svelte";
import type { ImageGET, StudyGET } from "../../types/openapi_types";

const MODALITY_LABELS: Record<string, string> = {
    AdaptiveOptics: "AO",
    ColorFundus: "CFI",
    ColorFundusStereo: "CF Stereo",
    RedFreeFundus: "Red Free",
    ExternalEye: "External",
    LensPhotograph: "Lens",
    Ophthalmoscope: "OS",
    Autofluorescence: "AF",
    FluoresceinAngiography: "FA",
    ICGA: "ICGA",
    InfraredReflectance: "IR",
    BlueReflectance: "BR",
    GreenReflectance: "GR",
    OCT: "OCT",
    OCTA: "OCTA",
};

/** The tile caption: short modality, ETDRS field, and an OCT's frame count (v1). */
export function instanceLabel(instance: ImageGET): string {
    const parts: string[] = [];
    const modality = instance.modality
        ? MODALITY_LABELS[instance.modality]
        : undefined;
    if (modality) parts.push(modality);
    if (instance.etdrs_field) parts.push(instance.etdrs_field);
    if (instance.modality === "OCT") parts.push(`[${instance.nr_of_frames}]`);
    return parts.join(" ");
}

export function imageCount(n: number): string {
    return `${n} ${n === 1 ? "image" : "images"}`;
}

export type Laterality = "L" | "R" | null;

export function eyeName(laterality: Laterality): string {
    if (laterality === "R") return "OD";
    if (laterality === "L") return "OS";
    return "Laterality unknown";
}

/** A study's images of one eye, in series order; null is the unknown-laterality eye. */
export function eyeImages(study: StudyGET, laterality: Laterality): ImageGET[] {
    return (study.series ?? [])
        .flatMap((series) => series.instance_ids ?? [])
        .map((id) => instances.get(id))
        .filter(
            (i): i is ImageGET =>
                i !== undefined && (i.laterality ?? null) === laterality,
        );
}
