import { afterEach, describe, expect, it } from "vitest";
import type { PhotoLocator } from "$lib/registration/photoLocators";
import { LocalizerLines } from "./localizerLines.svelte";

afterEach(() => localStorage.clear());

const lines = () => [{} as PhotoLocator];

describe("LocalizerLines", () => {
    it("starts on the browser's last choice, Off when there is none or it is unknown", () => {
        expect(new LocalizerLines(lines).mode).toBe("off");
        localStorage.setItem("eyened:viewer:localizer", "lines");
        expect(new LocalizerLines(lines).mode).toBe("off");
        localStorage.setItem("eyened:viewer:localizer", "all");
        expect(new LocalizerLines(lines).mode).toBe("all");
    });

    it("O switches between Off and the last other mode, Current at first, and saves every change", () => {
        const localizer = new LocalizerLines(lines);
        localizer.toggle();
        expect(localizer.mode).toBe("current");
        localizer.set("all");
        localizer.toggle();
        expect(localizer.mode).toBe("off");
        expect(localStorage.getItem("eyened:viewer:localizer")).toBe("off");
        localizer.toggle();
        expect(localizer.mode).toBe("all");
    });

    it("O turns a stored non-Off choice back on after switching it off", () => {
        localStorage.setItem("eyened:viewer:localizer", "all");
        const localizer = new LocalizerLines(lines);
        localizer.toggle();
        localizer.toggle();
        expect(localizer.mode).toBe("all");
    });

    it("O does nothing on an image without localizer lines", () => {
        const localizer = new LocalizerLines(() => []);
        localizer.toggle();
        expect(localizer.mode).toBe("off");
        expect(localStorage.getItem("eyened:viewer:localizer")).toBeNull();
    });
});
