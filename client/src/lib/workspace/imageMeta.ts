import type { ImageGET } from "../../types/openapi_types";
import { eyeRank, modalityRank, type CatalogueEntry } from "./workspaceRules";

export type ImageMeta = Pick<
    ImageGET,
    "patient" | "study" | "modality" | "etdrs_field" | "laterality" | "device"
>;

/** A viewport title: the patient ID, never shortened, and the rest, which may end in an ellipsis. */
export interface ViewportTitle {
    patient: string;
    rest: string;
}

const MODALITY_LABELS: Partial<Record<string, string>> = {
    ColorFundus: "CF",
    InfraredReflectance: "IR",
    Autofluorescence: "FAF",
    OCT: "OCT",
};

export function viewportTitle(meta: ImageMeta): ViewportTitle {
    const eye =
        meta.laterality === "R" ? "OD" : meta.laterality === "L" ? "OS" : null;
    const modality = meta.modality
        ? (MODALITY_LABELS[meta.modality] ?? meta.modality)
        : null;
    const field =
        modality && meta.etdrs_field
            ? `${modality} ${meta.etdrs_field}`
            : modality;
    const device = [meta.device.manufacturer, meta.device.model]
        .filter(Boolean)
        .join(" ");
    return {
        patient: meta.patient.identifier,
        rest: [eye, field, meta.study.date, device].filter(Boolean).join(" · "),
    };
}

export function titleText(title: ViewportTitle): string {
    return title.rest ? `${title.patient} ${title.rest}` : title.patient;
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
