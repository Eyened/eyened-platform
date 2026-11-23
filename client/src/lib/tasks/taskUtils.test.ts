import { afterEach, describe, expect, it, vi } from "vitest";
import { navigateSubtaskIndex } from "./taskUtils.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("navigateSubtaskIndex", () => {
    it("opens the set after index 4 as set 5, keeping layout= and arrange= only", () => {
        // jsdom ignores href assignments on the real location, so stub it.
        const location = {
            href: "http://localhost/tasks/12/set/4?layout=2x2&arrange=eye&v=img01,img02&page=2",
            pathname: "/tasks/12/set/4",
            search: "?layout=2x2&arrange=eye&v=img01,img02&page=2",
        };
        vi.stubGlobal("location", location);
        navigateSubtaskIndex(4);
        expect(location.href).toBe("/tasks/12/set/5?layout=2x2&arrange=eye");
    });
});
