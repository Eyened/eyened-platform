import { describe, it, expect, beforeEach, vi } from "vitest";
import {
    TASK_PANEL_EXPANDED_STORAGE_KEY,
    getTaskPanelExpanded,
    setTaskPanelExpanded,
} from "./taskPanelExpandedPrefs";

describe("taskPanelExpandedPrefs", () => {
    beforeEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
    });

    it("returns the default when nothing is stored", () => {
        expect(getTaskPanelExpanded(7, false)).toBe(false);
        expect(getTaskPanelExpanded(7, true)).toBe(true);
    });

    it("round-trips per task id", () => {
        setTaskPanelExpanded(1, true);
        setTaskPanelExpanded(2, false);
        expect(getTaskPanelExpanded(1, false)).toBe(true);
        expect(getTaskPanelExpanded(2, true)).toBe(false);
    });

    it("returns the default when JSON is malformed", () => {
        localStorage.setItem(TASK_PANEL_EXPANDED_STORAGE_KEY, "{not json");
        expect(getTaskPanelExpanded(1, false)).toBe(false);
    });

    it("returns the default when stored JSON is not an object", () => {
        localStorage.setItem(TASK_PANEL_EXPANDED_STORAGE_KEY, "[]");
        expect(getTaskPanelExpanded(1, true)).toBe(true);
    });

    it("does not throw when localStorage.setItem throws", () => {
        vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
            throw new Error("quota");
        });
        expect(() => setTaskPanelExpanded(1, true)).not.toThrow();
    });

    it("does not throw when localStorage.getItem throws", () => {
        vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
            throw new Error("blocked");
        });
        expect(getTaskPanelExpanded(1, false)).toBe(false);
    });
});
