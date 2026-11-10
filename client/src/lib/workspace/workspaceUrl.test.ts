import { afterEach, describe, expect, it, vi } from "vitest";
import {
    createWorkspaceUrlWriter,
    parseWorkspaceParams,
    writeWorkspaceParams,
    type WorkspaceUrlState,
} from "./workspaceUrl";

const state: WorkspaceUrlState = {
    v: [{ id: "aaa", index: 42 }, null, { id: "bbb_proj" }],
    layout: "3x1",
    page: 2,
    arrange: "eye",
};

afterEach(() => {
    vi.useRealTimers();
});

describe("workspaceUrl", () => {
    it("round-trips every param, keeping empty v= entries by position", () => {
        const params = writeWorkspaceParams(
            new URLSearchParams("instances=aaa,bbb"),
            state,
        );
        expect(params.get("v")).toBe("aaa.42,,bbb_proj");
        expect(params.get("instances")).toBe("aaa,bbb");
        expect(parseWorkspaceParams(params)).toEqual(state);
    });

    it("drops defaults (Opened order among them) and ignores unknown values", () => {
        const written = writeWorkspaceParams(
            new URLSearchParams("layout=bogus&page=4&arrange=eye"),
            { v: [null], layout: "1x1", page: 1, arrange: "opened" },
        );
        expect(written.toString()).toBe("layout=1x1");
        expect(
            parseWorkspaceParams(
                new URLSearchParams("layout=bogus&page=x&arrange=nope"),
            ),
        ).toMatchObject({ layout: null, page: 1, arrange: "opened" });
        expect(parseWorkspaceParams(new URLSearchParams()).arrange).toBe(
            "opened",
        );
    });

    it("writes only the latest state once the delay has passed", () => {
        vi.useFakeTimers();
        const replaceUrl = vi.fn();
        const writer = createWorkspaceUrlWriter({
            getSearchParams: () => new URLSearchParams(),
            replaceUrl,
        });
        writer.write({ ...state, page: 2 });
        writer.write({ ...state, page: 3 });
        expect(replaceUrl).not.toHaveBeenCalled();
        vi.advanceTimersByTime(250);
        expect(replaceUrl).toHaveBeenCalledTimes(1);
        expect(replaceUrl.mock.calls[0][0].get("page")).toBe("3");
    });
});
