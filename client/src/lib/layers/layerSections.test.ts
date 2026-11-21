import { describe, expect, it } from "vitest";
import { layerSections } from "./layerSections";

const flat = {
    is2D: true,
    hasEtdrsSchema: true,
    hasRegistrationSchema: true,
    projection: false,
    localizer: false,
    hide: [],
};

describe("layerSections", () => {
    it("gives a 2D image every section in panel order; a volume or a missing schema drops ETDRS grids and Pointsets", () => {
        expect(layerSections(flat)).toEqual([
            "segmentations",
            "etdrs",
            "pointsets",
            "registration",
            "blend",
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
        ).toEqual(["segmentations", "pointsets", "registration", "blend"]);
    });

    it("adds En-face projection after Distance lines; layout.hide Segmentation hides it too", () => {
        expect(layerSections({ ...flat, projection: true })).toEqual([
            "segmentations",
            "etdrs",
            "pointsets",
            "registration",
            "blend",
            "distance",
            "projection",
        ]);
        expect(
            layerSections({
                ...flat,
                projection: true,
                hide: ["Segmentation"],
            }),
        ).toEqual(["etdrs", "pointsets", "registration", "blend", "distance"]);
    });

    it("adds Localizer lines last, which no layout.hide name hides", () => {
        expect(
            layerSections({
                ...flat,
                localizer: true,
                hide: ["Segmentation", "ETDRS", "Registration", "Measure"],
            }),
        ).toEqual(["localizer"]);
    });

    it("puts Blend after Pointsets on 2D images with the registration schema, and hides both with Registration", () => {
        const input = {
            is2D: true,
            hasEtdrsSchema: false,
            hasRegistrationSchema: true,
            projection: false,
            localizer: false,
            hide: [] as string[],
        };
        expect(layerSections(input)).toEqual([
            "segmentations",
            "pointsets",
            "registration",
            "blend",
            "distance",
        ]);
        expect(layerSections({ ...input, hide: ["Registration"] })).toEqual([
            "segmentations",
            "distance",
        ]);
    });
});
