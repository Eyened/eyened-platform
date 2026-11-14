import { afterEach, describe, expect, it } from "vitest";
import { instances } from "$lib/data/stores.svelte";
import { octLabel } from "./octLabel";

afterEach(() => instances.clear());

const oct = (anatomic_region: string) =>
    ({ anatomic_region, study: { date: "2024-03-12" } }) as never;

describe("octLabel", () => {
    it("names macula and disc, and leaves out a region it does not know", () => {
        instances.set("oct-1", oct("2"));
        instances.set("oct-2", oct("0"));
        expect(octLabel("oct-1", 49)).toBe(
            "OCT 2024-03-12 · macula · 49 B-scans",
        );
        expect(octLabel("oct-2", 49)).toBe("OCT 2024-03-12 · 49 B-scans");
    });
});
