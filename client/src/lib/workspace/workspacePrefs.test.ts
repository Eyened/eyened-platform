import { afterEach, describe, expect, it } from "vitest";
import { MAGNIFIER_DEFAULTS } from "./magnifier";
import { PAINT_DEFAULTS } from "./paint";
import { mockWidth } from "./testUtils";
import { Workspace } from "./workspace.svelte";
import {
    readMagnifier,
    readLayerArea,
    readLayerSections,
    readPaint,
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

describe("strip tracking", () => {
    it("starts on", () => {
        expect(readStripTracking()).toBe(true);
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
    it("start with Segmentations open, restore the last open set, and ignore a bad value", () => {
        expect(readLayerSections()).toEqual({
            segmentations: true,
            etdrs: false,
            pointsets: false,
            blend: false,
            distance: false,
            projection: false,
            localizer: false,
        });
        writeLayerSections({
            segmentations: false,
            etdrs: true,
            pointsets: false,
            blend: false,
            distance: true,
            projection: true,
            localizer: true,
        });
        expect(readLayerSections()).toEqual({
            segmentations: false,
            etdrs: true,
            pointsets: false,
            blend: false,
            distance: true,
            projection: true,
            localizer: true,
        });
        localStorage.setItem("eyened:viewer:layerSections", "{");
        expect(readLayerSections().segmentations).toBe(true);
    });
});

describe("magnifier", () => {
    it("round-trips what the grader set", () => {
        new Workspace().setMagnifier({
            on: true,
            zoom: 6,
            size: "large",
            corner: 2,
            x: 40,
            y: 120,
        });
        expect(readMagnifier()).toEqual({
            on: true,
            zoom: 6,
            size: "large",
            corner: 2,
            x: 40,
            y: 120,
        });
    });

    it("gives the defaults (off, 3×, Medium, start corner) for a missing or bad value", () => {
        expect(readMagnifier()).toEqual(MAGNIFIER_DEFAULTS);
        localStorage.setItem("eyened:viewer:magnifier", "{not json");
        expect(readMagnifier()).toEqual(MAGNIFIER_DEFAULTS);
        localStorage.setItem(
            "eyened:viewer:magnifier",
            JSON.stringify({
                on: "yes",
                zoom: 5,
                size: "toString",
                corner: 7,
                x: "1",
            }),
        );
        expect(readMagnifier()).toEqual(MAGNIFIER_DEFAULTS);
    });
});

describe("readPaint", () => {
    it("keeps each valid stored field and falls back per field to the default", () => {
        localStorage.setItem(
            "eyened:viewer:paint",
            JSON.stringify({
                size2D: 12,
                sizeBscan: 2000,
                hardness: "soft",
                pressure: 0.8,
            }),
        );
        expect(readPaint()).toEqual({
            size2D: 12,
            sizeBscan: 4,
            hardness: 0.5,
            pressure: 0.8,
        });
        localStorage.setItem("eyened:viewer:paint", "{not json");
        expect(readPaint()).toEqual(PAINT_DEFAULTS);
    });
});
