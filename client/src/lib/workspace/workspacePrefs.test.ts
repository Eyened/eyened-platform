import { afterEach, describe, expect, it } from "vitest";
import { MAGNIFIER_DEFAULTS } from "./magnifier";
import { mockWidth } from "./testUtils";
import { Workspace } from "./workspace.svelte";
import {
    readMagnifier,
    readLayerArea,
    readLayerSections,
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
    it("start with Segmentations open, restore the last open set except Distance lines, and ignore a bad value", () => {
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
            distance: false,
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
            x: 40,
            y: 120,
        });
        expect(readMagnifier()).toEqual({
            on: true,
            zoom: 6,
            size: "large",
            x: 40,
            y: 120,
        });
    });

    it("gives the defaults (off, 3×, Medium, top-right) for a missing or bad value", () => {
        expect(readMagnifier()).toEqual(MAGNIFIER_DEFAULTS);
        localStorage.setItem("eyened:viewer:magnifier", "{not json");
        expect(readMagnifier()).toEqual(MAGNIFIER_DEFAULTS);
        localStorage.setItem(
            "eyened:viewer:magnifier",
            JSON.stringify({ on: "yes", zoom: 5, size: "toString", x: "1" }),
        );
        expect(readMagnifier()).toEqual(MAGNIFIER_DEFAULTS);
    });
});
