import { afterEach, describe, expect, it } from "vitest";
import { mockWidth } from "./testUtils";
import { startStripOn, writeStripOn } from "./workspacePrefs";

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
