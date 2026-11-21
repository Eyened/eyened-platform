import { describe, expect, it } from "vitest";
import { paneHeight } from "./paneHeight";

describe("paneHeight", () => {
    it("keeps a set height within the tab: the list keeps 96 px and the pane at least 80", () => {
        // A 500 px tab leaves the list 96 px: at most 404.
        expect(paneHeight(600, 500)).toBe(404);
        expect(paneHeight(50, 500)).toBe(80);
        // A tab shorter than both minimums still gives the pane its own.
        expect(paneHeight(300, 150)).toBe(80);
    });
});
