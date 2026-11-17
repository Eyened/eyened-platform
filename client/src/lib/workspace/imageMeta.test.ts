import { describe, expect, it } from "vitest";
import {
    catalogueEntry,
    titleText,
    twinNumbers,
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

describe("twinNumbers", () => {
    /** The shared fixture under another public ID. */
    const twin = (id: string, over: object = {}) =>
        ({ ...meta, id, ...over }) as ImageMeta;

    it("numbers same-titled images of different instances in strip order, not load or id order, and renumbers when the first closes", () => {
        // Loaded c, a, b; ids sort a, b, c; the strip shows b, c, a.
        const loaded = new Map([
            ["c", twin("c")],
            ["a", twin("a")],
            ["b", twin("b")],
        ]);
        const numbers = (strip: string[]) => {
            const twins = twinNumbers(strip, (id) => loaded.get(id));
            return strip.map((id) => twins.get(id) ?? "");
        };
        expect(numbers(["b", "c", "a"])).toEqual(["", "#2", "#3"]);
        expect(numbers(["c", "a"])).toEqual(["", "#2"]);
    });

    it("does not number a different field, model, date, eye or patient, nor an OCT volume and its projection", () => {
        const loaded: Record<string, ImageMeta> = {
            first: twin("first"),
            field: twin("field", { etdrs_field: "F2" }),
            model: twin("model", {
                device: { manufacturer: "Topcon", model: "Maestro2" },
            }),
            date: twin("date", { study: { id: 1, date: "2023-05-05" } }),
            eye: twin("eye", { laterality: "L" }),
            patient: twin("patient", {
                patient: { id: 2, identifier: "P-000418" },
            }),
            oct: twin("oct", { modality: "OCT" }),
            // The projection shares its volume's instance.
            oct_proj: twin("oct", { modality: "OCT" }),
        };
        expect(twinNumbers(Object.keys(loaded), (id) => loaded[id]).size).toBe(
            0,
        );
    });
});
