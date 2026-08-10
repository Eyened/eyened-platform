import { describe, it, expect } from "vitest";
import {
    parseViewersParam,
    serializeViewersParam,
    parseStoredState,
    serializeStoredState,
    storageKey,
    createViewerViewStateController,
    VIEW_STATE_PARAM,
    instanceIdFromImageId,
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

describe("parseViewersParam / serializeViewersParam", () => {
    it("round-trips id.index and bare ids", () => {
        const viewers = [
            { id: "aaa", index: 42 },
            { id: "bbb_proj" },
            { id: "ccc", index: 10 },
        ];
        expect(parseViewersParam(serializeViewersParam(viewers))).toEqual(
            viewers,
        );
    });

    it("returns empty for null/empty", () => {
        expect(parseViewersParam(null)).toEqual([]);
        expect(parseViewersParam("")).toEqual([]);
        expect(parseViewersParam(undefined)).toEqual([]);
    });

    it("ignores malformed tokens", () => {
        expect(
            parseViewersParam("aaa.42,bad!,bbb.x,ccc.-1,ddd.3.5,eee.7,fff"),
        ).toEqual([
            { id: "aaa", index: 42 },
            { id: "eee", index: 7 },
            { id: "fff" },
        ]);
    });

    it("omits empty serialize", () => {
        expect(serializeViewersParam([])).toBe("");
    });

    it("does not percent-encode dots in typical ids", () => {
        const encoded = serializeViewersParam([
            { id: "q4m7gj6h", index: 119 },
            { id: "vc88pyyh", index: 15 },
        ]);
        expect(encoded).toBe("q4m7gj6h.119,vc88pyyh.15");
        expect(encoded.includes("%")).toBe(false);
        expect(encoded.includes(":")).toBe(false);
    });
});

describe("parseStoredState / serializeStoredState", () => {
    it("round-trips v2 payload", () => {
        const state = {
            version: 2 as const,
            viewers: [{ id: "a", index: 1 }, { id: "b" }],
        };
        expect(parseStoredState(serializeStoredState(state))).toEqual(state);
    });

    it("returns null for invalid or legacy payloads", () => {
        expect(parseStoredState(null)).toBeNull();
        expect(parseStoredState("{")).toBeNull();
        expect(
            parseStoredState(JSON.stringify({ version: 1, frames: {} })),
        ).toBeNull();
        expect(parseStoredState(JSON.stringify({ version: 2 }))).toBeNull();
    });
});

describe("storageKey / instanceIdFromImageId", () => {
    it("prefixes scope", () => {
        expect(storageKey("view")).toBe("eyened:viewerViewState:view");
        expect(storageKey("subtask:99")).toBe(
            "eyened:viewerViewState:subtask:99",
        );
    });

    it("strips _proj suffix", () => {
        expect(instanceIdFromImageId("abc_proj")).toBe("abc");
        expect(instanceIdFromImageId("abc")).toBe("abc");
    });
});

describe("createViewerViewStateController", () => {
    it(`prefers URL ${VIEW_STATE_PARAM} over localStorage on hydrate`, () => {
        const storage = memoryStorage();
        storage.setItem(
            "eyened:viewerViewState:view",
            JSON.stringify({
                version: 2,
                viewers: [{ id: "aaa", index: 1 }],
            }),
        );
        let params = new URLSearchParams("v=aaa.9,bbb");
        const c = createViewerViewStateController({
            scope: "view",
            getSearchParams: () => params,
            replaceUrl: (p) => {
                params = new URLSearchParams(p);
            },
            storage,
        });
        c.hydrate();
        expect(c.getViewers()).toEqual([
            { id: "aaa", index: 9 },
            { id: "bbb" },
        ]);
        c.enableRecording();
        expect(params.get("v")).toBe("aaa.9,bbb");
        expect(params.get("frame")).toBeNull();
    });

    it("falls back to localStorage when URL empty", () => {
        const storage = memoryStorage();
        storage.setItem(
            "eyened:viewerViewState:subtask:5",
            JSON.stringify({
                version: 2,
                viewers: [{ id: "aaa", index: 3 }],
            }),
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
        expect(c.peekIndex("aaa", 10)).toBe(3);
        c.enableRecording();
        expect(params.get("v")).toBe("aaa.3");
    });

    it("ignores recordIndex until enableRecording and only for open viewers", () => {
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
        c.setOpenViewers([{ id: "aaa" }]);
        c.recordIndex("aaa", 4, 10);
        expect(params.get("v")).toBeNull();
        c.enableRecording();
        expect(params.get("v")).toBe("aaa");
        c.recordIndex("aaa", 4, 10);
        expect(params.get("v")).toBe("aaa.4");
        c.recordIndex("zzz", 1, 10);
        expect(params.get("v")).toBe("aaa.4");
    });

    it("peekIndex rejects out-of-range; prune drops stale instance viewers", () => {
        let params = new URLSearchParams("v=aaa.50,bbb.2,ccc_proj");
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
        expect(c.peekIndex("aaa", 10)).toBeUndefined();
        expect(c.peekIndex("bbb", 10)).toBe(2);
        c.enableRecording();
        c.prune(["bbb", "ccc"]);
        expect(params.get("v")).toBe("bbb.2,ccc_proj");
    });
});
