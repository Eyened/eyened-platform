import { describe, it, expect } from "vitest";
import {
    parseFrameParam,
    serializeFrameParam,
    parseStoredState,
    serializeStoredState,
    storageKey,
} from "./viewerViewState";

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
