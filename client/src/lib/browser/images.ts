import type { ImageGET } from "../../types/openapi_types";

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
