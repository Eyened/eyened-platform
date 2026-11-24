import { describe, expect, it } from "vitest";
import {
    ageAt,
    catalogueEntry,
    imageName,
    imageRowName,
    octPart,
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

describe("ageAt", () => {
    it("counts whole years, one less until the birthday", () => {
        expect(ageAt("1951-06-15", "2024-06-14")).toBe(72);
        expect(ageAt("1951-06-15", "2024-06-15")).toBe(73);
        expect(ageAt("2000-02-29", "2023-02-28")).toBe(22);
    });

    it("is unknown without a birth date or when the birth is after the visit", () => {
        expect(ageAt(null, "2024-06-14")).toBeNull();
        expect(ageAt("2025-01-01", "2024-06-14")).toBeNull();
    });
});

describe("viewportTitle demographics", () => {
    it("puts sex and age at the visit after the ID, and says them in words", () => {
        const title = viewportTitle({
            ...meta,
            patient: {
                id: 1,
                identifier: "P-000417",
                birth_date: "1951-06-15",
                sex: "F",
            },
            study: { id: 1, date: "2024-03-12" },
        });
        expect(title.demographics).toBe("F · 72 y");
        expect(title.demographicsText).toBe("female, 72 years");
        expect(titleText(title)).toBe(
            "P-000417 · F · 72 y OD · CF F1 · 2024-03-12 · Topcon TRC-NW8",
        );
    });

    it("keeps the sex alone when the birth date is unknown", () => {
        const title = viewportTitle({
            ...meta,
            patient: {
                id: 1,
                identifier: "P-000417",
                birth_date: null,
                sex: "F",
            },
        });
        expect([title.demographics, title.demographicsText]).toEqual([
            "F",
            "female",
        ]);
    });

    it('says "0 y" under a year', () => {
        const title = viewportTitle({
            ...meta,
            patient: {
                id: 1,
                identifier: "P-000417",
                birth_date: "2024-01-10",
                sex: "F",
            },
            study: { id: 1, date: "2024-06-14" },
        });
        expect(title.demographics).toBe("F · 0 y");
    });
});

describe("an OCT's two images", () => {
    const open = new Set(["oct-1", "oct-1_proj", "oct-2"]);
    const isOpen = (id: string) => open.has(id);

    it("tells the en-face from the B-scans, and leaves a lone volume as OCT", () => {
        expect(octPart("oct-1_proj", isOpen)).toBe("enface");
        expect(octPart("oct-1", isOpen)).toBe("bscans");
        expect(octPart("oct-2", isOpen)).toBeUndefined();
    });

    it("uses the same words in viewport titles, Images rows and Layers names", () => {
        const oct = {
            ...meta,
            modality: "OCT",
            etdrs_field: null,
        } as ImageMeta;
        expect(viewportTitle(oct, { oct: "enface" }).rest).toBe(
            "OCT en-face · 2023-05-04 · Topcon TRC-NW8",
        );
        expect(imageRowName(oct, "bscans")).toBe("OD · OCT B-scans");
        expect(imageName(oct, "", "enface").name).toBe(
            "OCT en-face · 2023-05-04",
        );
    });
});
