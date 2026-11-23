import { describe, expect, it } from "vitest";
import { layerSections } from "./layerSections";

const flat = {
    is2D: true,
    hasEtdrsSchema: true,
    hasRegistrationSchema: true,
    hide: [],
};

describe("layerSections", () => {
    it("gives a 2D image every section in panel order; a volume or a missing schema drops ETDRS grids and Pointsets", () => {
        expect(layerSections(flat)).toEqual([
            "segmentations",
            "etdrs",
            "pointsets",
            "distance",
        ]);
        expect(layerSections({ ...flat, is2D: false })).toEqual([
            "segmentations",
            "distance",
        ]);
        expect(
            layerSections({
                ...flat,
                hasEtdrsSchema: false,
                hasRegistrationSchema: false,
            }),
        ).toEqual(["segmentations", "distance"]);
    });

    it("maps the task's layout.hide panel names onto sections", () => {
        expect(
            layerSections({ ...flat, hide: ["Segmentation", "Registration"] }),
        ).toEqual(["etdrs", "distance"]);
        expect(
            layerSections({ ...flat, hide: ["ETDRS", "Measure", "Form"] }),
        ).toEqual(["segmentations", "pointsets"]);
    });
});
