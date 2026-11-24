import { describe, expect, it } from "vitest";
import { armedSection, searchHelp } from "./helpKeys";

const shape = (query: string) =>
    searchHelp(query).sections.map((s) => [
        s.title,
        s.tools.map((t) => [t.name, t.rows.map((r) => r.keys)]),
        s.rows.map((r) => r.keys),
    ]);

describe("searchHelp", () => {
    it('"space" finds the six key rows that press or hold Space', () => {
        expect(searchHelp("space").count).toBe(6);
        expect(shape("space")).toEqual([
            [
                "Draw",
                [
                    ["Brush", ["Hold Space"]],
                    ["Eraser", ["Hold Space"]],
                    ["Enhance", ["Hold Space"]],
                ],
                [],
            ],
            ["Place", [["Place ETDRS grid", ["Hold Space"]]], []],
            ["Keyboard cursor", [], ["Space", "Hold Space + arrows"]],
        ]);
    });

    it("ignores case, and a tool with no key rows still counts its own key", () => {
        expect(searchHelp("SPACE").count).toBe(6);
        expect(searchHelp("reset view").count).toBe(1);
    });
});

describe("armedSection", () => {
    it("is the armed tool's group; an armed form point field is Place; nothing armed opens none", () => {
        expect(armedSection("brush", false)).toBe("Draw");
        expect(armedSection("point", false)).toBe("Place");
        expect(armedSection(null, true)).toBe("Place");
        expect(armedSection(null, false)).toBeNull();
    });
});
