import { afterEach, describe, expect, it, vi } from "vitest";
import {
    dropFormAnnotationSaver,
    formAnnotationSaver,
    formAnnotationSavers,
} from "./formAnnotationSavers";
import { saveTracker } from "./saveTracker.svelte";

vi.mock("$lib/data", () => ({
    putFormAnnotationValue: vi.fn(async () => {}),
    storeFormAnnotationValue: vi.fn(),
}));
const { putFormAnnotationValue } = await import("$lib/data");

afterEach(() => vi.useRealTimers());

describe("dropFormAnnotationSaver", () => {
    it("a deleted form's waiting edit is never sent and leaves nothing unsaved", async () => {
        vi.useFakeTimers();
        const saver = formAnnotationSaver(7, "form", {
            to: "focus",
            focus: () => {},
        });
        saver.edit({ quality: "good" });
        dropFormAnnotationSaver(7);
        await vi.advanceTimersByTimeAsync(1000);
        expect(putFormAnnotationValue).not.toHaveBeenCalled();
        expect(saveTracker.savers).not.toContain(saver);
        expect(formAnnotationSavers.has(7)).toBe(false);
    });
});
