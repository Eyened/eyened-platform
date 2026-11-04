import { describe, expect, it } from "vitest";
import { getPreset } from "./presets";
import {
    changePreset,
    eyeRank,
    firstScreenPair,
    frameSetNeighbour,
    modalityRank,
    sortCatalogue,
    splitRange,
    splitterSegments,
    swapSlots,
    type ArrangeOrder,
    type CatalogueEntry,
    type Slot,
} from "./workspaceRules";

const entry = (
    imageId: string,
    over: Partial<CatalogueEntry> = {},
): CatalogueEntry => ({
    imageId,
    patient: "P-000417",
    date: "2023-05-04",
    modalityRank: 0,
    eyeRank: 0,
    ...over,
});
const ids = (slots: readonly Slot[]) => slots.map((s) => s.imageId);
const slotsOf = (...imageIds: (string | null)[]): Slot[] =>
    imageIds.map((imageId, i) => ({ id: i + 1, imageId }));
const preset = (id: string) => getPreset(id)!;

describe("sortCatalogue", () => {
    const open = [
        entry("b-os-cf", {
            patient: "P-2",
            eyeRank: eyeRank("L"),
            modalityRank: modalityRank("ColorFundus", "F1"),
            date: "2023-01-01",
        }),
        entry("a-od-oct", {
            patient: "P-1",
            eyeRank: eyeRank("R"),
            modalityRank: modalityRank("OCT"),
            date: "2024-01-01",
        }),
        entry("a-os-ir", {
            patient: "P-1",
            eyeRank: eyeRank("L"),
            modalityRank: modalityRank("InfraredReflectance"),
            date: "2023-01-01",
        }),
        entry("a-od-ir", {
            patient: "P-1",
            eyeRank: eyeRank("R"),
            modalityRank: modalityRank("InfraredReflectance"),
            date: "2023-01-01",
        }),
        entry("a-od-cf2", {
            patient: "P-1",
            eyeRank: eyeRank("R"),
            modalityRank: modalityRank("ColorFundus", "F2"),
            date: "2024-01-01",
        }),
    ];
    const order = (o: ArrangeOrder) =>
        sortCatalogue(open, o).map((e) => e.imageId);

    it("By visit: patient, visit date, modality, eye", () => {
        expect(order("visit")).toEqual([
            "a-od-ir",
            "a-os-ir",
            "a-od-cf2",
            "a-od-oct",
            "b-os-cf",
        ]);
    });

    it("Opened order keeps the order the images were opened, patient not first", () => {
        expect(order("opened")).toEqual([
            "b-os-cf",
            "a-od-oct",
            "a-os-ir",
            "a-od-ir",
            "a-od-cf2",
        ]);
    });

    it("By eye: patient, eye, modality, visit; by modality: patient, modality, visit, eye", () => {
        expect(order("eye")).toEqual([
            "a-od-cf2",
            "a-od-ir",
            "a-od-oct",
            "a-os-ir",
            "b-os-cf",
        ]);
        expect(order("modality")).toEqual([
            "a-od-cf2",
            "a-od-ir",
            "a-os-ir",
            "a-od-oct",
            "b-os-cf",
        ]);
    });
});

describe("swapSlots", () => {
    it("the two slots trade images and render keys; the others stay", () => {
        expect(swapSlots(slotsOf("i1", "i2", "i3"), 0, 2)).toEqual([
            { id: 3, imageId: "i3" },
            { id: 2, imageId: "i2" },
            { id: 1, imageId: "i1" },
        ]);
    });
});

describe("changePreset", () => {
    const catalogue = ["i1", "i2", "i3", "i4", "i5", "i6", "i7", "i8"];
    let next = 100;
    const newId = () => next++;

    it("opens the page holding the old page's first image; selection and views follow their images", () => {
        const r = changePreset({
            slots: slotsOf("i5", "i6"),
            selected: 1,
            catalogue,
            preset: preset("2x2"),
            newId,
        });
        expect(r.page).toBe(2);
        expect(ids(r.slots)).toEqual(["i5", "i6", "i7", "i8"]);
        expect(r.selected).toBe(1);
        expect(r.slots.slice(0, 2).map((s) => s.id)).toEqual([1, 2]);
    });
});

describe("frameSetNeighbour", () => {
    it("steps within the visit in By-visit order and stops at its ends", () => {
        const open = [
            entry("v1-oct", { modalityRank: 4 }),
            entry("v1-cf", { modalityRank: 0 }),
            entry("v2-cf", { date: "2024-01-01" }),
        ];
        expect(frameSetNeighbour(open, "v1-cf", 1)).toBe("v1-oct");
        expect(frameSetNeighbour(open, "v1-oct", 1)).toBeNull();
        expect(frameSetNeighbour(open, "v1-cf", -1)).toBeNull();
    });
});

describe("firstScreenPair", () => {
    it("pairs the first opened en-face image with an OCT of the same eye and visit", () => {
        const open = [
            entry("ir-os", { eyeRank: 1 }),
            entry("oct-od", { modalityRank: 4 }),
            entry("ir-od"),
            entry("oct-os", { eyeRank: 1, modalityRank: 4 }),
        ];
        const pairs = [
            { enfaceImageId: "ir-od", octImageId: "oct-od" },
            { enfaceImageId: "ir-os", octImageId: "oct-od" },
            { enfaceImageId: "ir-os", octImageId: "oct-os" },
        ];
        expect(firstScreenPair(open, pairs)).toEqual(["ir-os", "oct-os"]);
        expect(firstScreenPair(open, [pairs[1]])).toBeNull();
    });
});

describe("splitterSegments", () => {
    it("stops short of a spanning cell", () => {
        expect(splitterSegments(preset("3+2"))).toEqual([
            { axis: "col", line: 1, from: 0, to: 1 },
            { axis: "col", line: 2, from: 1, to: 2 },
            { axis: "col", line: 3, from: 0, to: 1 },
            { axis: "row", line: 1, from: 0, to: 4 },
        ]);
    });
});

describe("splitRange", () => {
    it("stops where a viewport would go below 160 px", () => {
        const r = splitRange(preset("2x1"), [1, 1], "col", 1, 1000);
        expect(r.lo * r.perFr).toBeCloseTo(160);
        expect((r.total - r.hi) * r.perFr).toBeCloseTo(160);
    });
    it("doesn't move when the viewports are already below the minimum", () => {
        const r = splitRange(preset("4x1"), [1, 1, 1, 1], "col", 2, 500);
        expect([r.lo, r.hi]).toEqual([1, 1]);
    });
});
