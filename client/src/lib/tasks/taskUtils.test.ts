import { afterEach, describe, expect, it, vi } from "vitest";
import { navigateSubtaskIndex } from "./taskUtils.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("navigateSubtaskIndex", () => {
    it("keeps layout= and arrange= and drops the rest of the query", () => {
        // jsdom ignores href assignments on the real location, so stub it.
        const location = {
            href: "http://localhost/tasks/12/grade/3?layout=2x2&arrange=eye&v=img01,img02&page=2",
            pathname: "/tasks/12/grade/3",
            search: "?layout=2x2&arrange=eye&v=img01,img02&page=2",
        };
        vi.stubGlobal("location", location);
        navigateSubtaskIndex(4);
        expect(location.href).toBe("/tasks/12/grade/4?layout=2x2&arrange=eye");
    });
});
