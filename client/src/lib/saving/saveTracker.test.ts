import { describe, expect, it } from "vitest";
import { SaveTracker, type Saver } from "./saveTracker.svelte";

function failed(kind: Saver["kind"], group: string): Saver {
    return {
        kind,
        group,
        target: { to: "focus", focus: () => {} },
        state: "error",
        flush: async () => {},
    };
}

describe("SaveTracker.text", () => {
    it("counts a segmentation once however many B-scans failed, and mixed kinds as items", () => {
        const tracker = new SaveTracker();
        tracker.edited = true;
        tracker.join(failed("segmentation", "grader_segmentation_7"));
        tracker.join(failed("segmentation", "grader_segmentation_7"));
        expect(tracker.text).toBe("1 segmentation couldn't save");
        tracker.join(failed("registration", "form-annotation-12"));
        expect(tracker.text).toBe("2 items couldn't save");
    });
});
