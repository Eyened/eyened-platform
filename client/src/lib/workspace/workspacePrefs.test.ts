import { afterEach, describe, expect, it } from "vitest";
import { mockWidth } from "./testUtils";
import {
    readLayerArea,
    readLayerSections,
    readStripLocalizer,
    readToolMode,
    readStripTracking,
    startStripOn,
    writeLayerArea,
    writeLayerSections,
    writeStripOn,
} from "./workspacePrefs";

afterEach(() => localStorage.clear());

describe("startStripOn", () => {
    it("starts the strip off on a narrow window, whatever config or storage says", () => {
        writeStripOn(true);
        mockWidth({ md: false, xlg: false });
        expect(startStripOn(true)).toBe(false);
        expect(startStripOn()).toBe(false);
        mockWidth({ md: true, xlg: false });
        expect(startStripOn(true)).toBe(true);
        expect(startStripOn()).toBe(true);
        expect(localStorage.getItem("eyened:viewer:strip")).toBe("true");
    });
});

describe("strip settings", () => {
    it("start on and All, and ignore a stored value they do not know", () => {
        expect(readStripTracking()).toBe(true);
        expect(readStripLocalizer()).toBe("all");
        localStorage.setItem("eyened:viewer:stripLocalizer", "lines");
        expect(readStripLocalizer()).toBe("all");
    });
});

describe("tool mode", () => {
    it("starts in Browse and ignores a stored value it does not know", () => {
        expect(readToolMode()).toBe("browse");
        localStorage.setItem("eyened:viewer:toolMode", "segment");
        expect(readToolMode()).toBe("browse");
        localStorage.setItem("eyened:viewer:toolMode", "all");
        expect(readToolMode()).toBe("all");
    });
});

describe("layer area", () => {
    it("starts on and remembers Off", () => {
        expect(readLayerArea()).toBe(true);
        writeLayerArea(false);
        expect(readLayerArea()).toBe(false);
    });
});

describe("Layers sections", () => {
    it("start with Segmentations open, restore the last open set except Distance lines, and ignore a bad value", () => {
        expect(readLayerSections()).toEqual({
            segmentations: true,
            etdrs: false,
            pointsets: false,
            distance: false,
        });
        writeLayerSections({
            segmentations: false,
            etdrs: true,
            pointsets: false,
            distance: true,
        });
        expect(readLayerSections()).toEqual({
            segmentations: false,
            etdrs: true,
            pointsets: false,
            distance: false,
        });
        localStorage.setItem("eyened:viewer:layerSections", "{");
        expect(readLayerSections().segmentations).toBe(true);
    });
});
