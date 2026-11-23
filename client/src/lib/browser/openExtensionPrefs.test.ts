import { beforeEach, describe, expect, it } from "vitest";
import {
    OPEN_EXTENSIONS_STORAGE_KEY,
    readOpenExtensionNames,
    writeOpenExtensionNames,
} from "./openExtensionPrefs";

describe("openExtensionPrefs", () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it("returns every name on a first visit", () => {
        expect(readOpenExtensionNames(["Registry", "Folded"])).toEqual([
            "Registry",
            "Folded",
        ]);
    });

    it("round-trips the open set", () => {
        writeOpenExtensionNames(["Registry"]);
        expect(readOpenExtensionNames(["Registry", "Folded"])).toEqual([
            "Registry",
        ]);
    });

    it("returns every name when JSON is malformed", () => {
        localStorage.setItem(OPEN_EXTENSIONS_STORAGE_KEY, "{not json");
        expect(readOpenExtensionNames(["Registry"])).toEqual(["Registry"]);
    });

    it("returns every name when stored JSON is not a string array", () => {
        localStorage.setItem(OPEN_EXTENSIONS_STORAGE_KEY, "null");
        expect(readOpenExtensionNames(["Registry"])).toEqual(["Registry"]);
    });
});
