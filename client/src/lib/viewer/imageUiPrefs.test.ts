import { beforeEach, describe, expect, it } from "vitest";
import { readOpacity, writeOpacity } from "./imageUiPrefs";

beforeEach(() => localStorage.clear());

describe("segmentation opacity", () => {
    it("is kept per image; a missing or bad value gives 1", () => {
        writeOpacity("inst-a", 0.4);
        expect(readOpacity("inst-a")).toBe(0.4);
        expect(readOpacity("inst-b")).toBe(1);
        localStorage.setItem(
            "eyened:imageUiPrefs",
            JSON.stringify({ "inst-b": { opacity: "60%" } }),
        );
        expect(readOpacity("inst-b")).toBe(1);
    });
});
