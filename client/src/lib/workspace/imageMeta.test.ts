import { describe, expect, it } from "vitest";
import {
    catalogueEntry,
    titleText,
    viewportTitle,
    type ImageMeta,
} from "./imageMeta";

const meta = {
    patient: { id: 1, identifier: "P-000417" },
    study: { id: 1, date: "2023-05-04" },
    modality: "ColorFundus",
    etdrs_field: "F1",
    laterality: "R",
    device: { manufacturer: "Topcon", model: "TRC-NW8" },
} as ImageMeta;

describe("viewportTitle", () => {
    it("puts the patient ID first, then eye, modality and field, date and device", () => {
        expect(titleText(viewportTitle(meta))).toBe(
            "P-000417 OD · CF F1 · 2023-05-04 · Topcon TRC-NW8",
        );
    });
});

describe("viewportTitle fallbacks", () => {
    it("drops what is unknown and keeps an unmapped modality as is", () => {
        const sparse = {
            ...meta,
            laterality: null,
            modality: "SLO",
            etdrs_field: null,
            device: {},
        } as unknown as ImageMeta;
        expect(titleText(viewportTitle(sparse))).toBe(
            "P-000417 SLO · 2023-05-04",
        );
    });

    it("titleText is just the patient when nothing else is known", () => {
        expect(titleText({ patient: "P-000417", rest: "" })).toBe("P-000417");
    });
});

describe("catalogueEntry", () => {
    it("takes patient and visit date from the metadata and ranks the image", () => {
        const e = catalogueEntry("img01", meta);
        expect(e).toMatchObject({
            imageId: "img01",
            patient: "P-000417",
            date: "2023-05-04",
        });
        expect(e.eyeRank).toBeLessThan(
            catalogueEntry("img02", { ...meta, laterality: "L" }).eyeRank,
        );
    });
});
