import { describe, it, expect } from "vitest";
import {
    parseFrameParam,
    serializeFrameParam,
    parseStoredState,
    serializeStoredState,
    storageKey,
    createViewerViewStateController,
} from "./viewerViewState";

function memoryStorage(): Pick<Storage, "getItem" | "setItem"> & {
    data: Record<string, string>;
} {
    const data: Record<string, string> = {};
    return {
        data,
        getItem: (k) => data[k] ?? null,
        setItem: (k, v) => {
            data[k] = v;
        },
    };
}

describe("parseFrameParam / serializeFrameParam", () => {
    it("round-trips id:index pairs", () => {
        const frames = { aaa: 42, bbb: 10 };
        expect(parseFrameParam(serializeFrameParam(frames))).toEqual(frames);
    });

    it("returns empty object for null/empty", () => {
        expect(parseFrameParam(null)).toEqual({});
        expect(parseFrameParam("")).toEqual({});
        expect(parseFrameParam(undefined)).toEqual({});
    });

    it("ignores malformed pairs and non-integer / negative indices", () => {
        expect(parseFrameParam("aaa:42,bad,bbb:x,ccc:-1,ddd:3.5,eee:7")).toEqual({
            aaa: 42,
            eee: 7,
        });
    });

    it("omits empty serialize", () => {
        expect(serializeFrameParam({})).toBe("");
    });
});

describe("parseStoredState / serializeStoredState", () => {
    it("round-trips v1 payload", () => {
        const state = { version: 1 as const, frames: { a: 1 } };
        expect(parseStoredState(serializeStoredState(state))).toEqual(state);
    });

    it("returns null for invalid JSON, wrong version, or missing frames", () => {
        expect(parseStoredState(null)).toBeNull();
        expect(parseStoredState("{")).toBeNull();
        expect(parseStoredState(JSON.stringify({ version: 2, frames: {} }))).toBeNull();
        expect(parseStoredState(JSON.stringify({ version: 1 }))).toBeNull();
    });
});

describe("storageKey", () => {
    it("prefixes scope", () => {
        expect(storageKey("view")).toBe("eyened:viewerViewState:view");
        expect(storageKey("subtask:99")).toBe("eyened:viewerViewState:subtask:99");
    });
});

describe("createViewerViewStateController", () => {
    it("prefers URL frame over localStorage on hydrate", () => {
        const storage = memoryStorage();
        storage.setItem(
            "eyened:viewerViewState:view",
            JSON.stringify({ version: 1, frames: { aaa: 1 } }),
        );
        let params = new URLSearchParams("frame=aaa:9");
        const replaced: string[] = [];
        const c = createViewerViewStateController({
            scope: "view",
            getSearchParams: () => params,
            replaceUrl: (p) => {
                replaced.push(p.toString());
                params = new URLSearchParams(p);
            },
            storage,
        });
        c.hydrate();
        expect(c.peekFrame("aaa", 100)).toBe(9);
        c.enableRecording();
        expect(params.get("frame")).toBe("aaa:9");
    });

    it("falls back to localStorage when URL frame empty", () => {
        const storage = memoryStorage();
        storage.setItem(
            "eyened:viewerViewState:subtask:5",
            JSON.stringify({ version: 1, frames: { aaa: 3 } }),
        );
        let params = new URLSearchParams();
        const c = createViewerViewStateController({
            scope: "subtask:5",
            getSearchParams: () => params,
            replaceUrl: (p) => {
                params = new URLSearchParams(p);
            },
            storage,
        });
        c.hydrate();
        expect(c.peekFrame("aaa", 10)).toBe(3);
    });

    it("ignores record until enableRecording", () => {
        let params = new URLSearchParams();
        const storage = memoryStorage();
        const c = createViewerViewStateController({
            scope: "view",
            getSearchParams: () => params,
            replaceUrl: (p) => {
                params = new URLSearchParams(p);
            },
            storage,
        });
        c.hydrate();
        c.record("aaa", 4, 10);
        expect(params.get("frame")).toBeNull();
        c.enableRecording();
        c.record("aaa", 4, 10);
        expect(params.get("frame")).toBe("aaa:4");
        expect(
            JSON.parse(storage.data["eyened:viewerViewState:view"]).frames.aaa,
        ).toBe(4);
    });

    it("peekFrame rejects out-of-range; prune drops stale ids", () => {
        let params = new URLSearchParams("frame=aaa:50,bbb:2");
        const storage = memoryStorage();
        const c = createViewerViewStateController({
            scope: "view",
            getSearchParams: () => params,
            replaceUrl: (p) => {
                params = new URLSearchParams(p);
            },
            storage,
        });
        c.hydrate();
        expect(c.peekFrame("aaa", 10)).toBeUndefined();
        expect(c.peekFrame("bbb", 10)).toBe(2);
        c.enableRecording();
        c.prune(["bbb"]);
        expect(params.get("frame")).toBe("bbb:2");
    });
});
