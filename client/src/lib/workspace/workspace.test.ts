import { describe, expect, it, vi } from "vitest";
import { entries, entry, NO_URL, workspaceWith } from "./testUtils";
import { Workspace } from "./workspace.svelte";

const ids = (ws: Workspace) => ws.slots.map((s) => s.imageId);

describe("Workspace.hydrate", () => {
    it("restores v= by position, keeping empty entries and emptying unknown images", () => {
        const ws = workspaceWith(6, {
            v: [{ id: "img02", index: 7 }, null, { id: "gone" }],
        });
        expect(ws.preset.id).toBe("3x1");
        expect(ids(ws)).toEqual(["img02", null, null]);
        expect(ws.peekIndex("img02", 20)).toBe(7);
    });

    it("opens the first-screen pair side by side", () => {
        const ws = new Workspace();
        ws.hydrate(entries(4), NO_URL, ["img03", "img01"]);
        expect(ws.preset.id).toBe("2x1");
        expect(ids(ws)).toEqual(["img03", "img01"]);
    });

    it("pages a named layout when v= names none of the open images", () => {
        const ws = workspaceWith(6, {
            v: [{ id: "other-set" }],
            layout: "2x2",
            page: 2,
        });
        expect(ids(ws)).toEqual(["img05", "img06", null, null]);
    });
});

describe("Workspace paging", () => {
    it("refills every slot and keeps the selection across a page turn, and writes the URL", () => {
        const writeUrl = vi.fn();
        const ws = workspaceWith(6, { layout: "2x2" }, writeUrl);
        ws.select(2);
        ws.turnPage(2);
        expect(ids(ws)).toEqual(["img05", "img06", null, null]);
        expect(ws.selected).toBe(2);
        expect(ws.pagerText).toBe("Images 5–6 of 6");
        expect(ws.announcement).toBe("Page 2 of 2, images 5–6");
        expect(writeUrl).toHaveBeenLastCalledWith(
            expect.objectContaining({ page: 2, layout: "2x2" }),
        );
    });
});

describe("Workspace edits", () => {
    it("empties slots whose instance left; added images wait for the next page turn", () => {
        const ws = workspaceWith(4, { layout: "2x1" });
        ws.prune(["img02", "img03", "img04"]);
        expect(ids(ws)).toEqual([null, "img02"]);
        expect(ws.announcement).toBe("1 viewport emptied");
        ws.addImages([entry("img00", { modalityRank: -1 })]);
        expect(ws.catalogue.at(-1)).toBe("img00");
        expect(ids(ws)).toEqual([null, "img02"]);
    });

    it("writes a recorded slice index into v= for a shown image", () => {
        const writeUrl = vi.fn();
        const ws = workspaceWith(2, {}, writeUrl);
        ws.recordIndex("img01", 12, 128);
        expect(writeUrl).toHaveBeenLastCalledWith(
            expect.objectContaining({ v: [{ id: "img01", index: 12 }] }),
        );
        expect(ws.peekIndex("img01", 10)).toBeUndefined();
    });

    it("Opened order comes back after another order; added images go last", () => {
        const ws = new Workspace();
        ws.hydrate(
            [
                entry("b", { patient: "P-000502" }),
                entry("a", { patient: "P-000417" }),
            ],
            { ...NO_URL, arrange: "opened" },
            null,
        );
        ws.setArrange("visit");
        expect(ws.catalogue).toEqual(["a", "b"]);
        ws.setArrange("opened");
        ws.addImages([entry("c", { patient: "P-000100" })]);
        expect(ws.catalogue).toEqual(["b", "a", "c"]);
    });
});
