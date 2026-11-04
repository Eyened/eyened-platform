import { describe, expect, it } from "vitest";
import { titleText, viewportTitle, type ImageMeta } from "./imageMeta";

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
