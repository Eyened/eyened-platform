import { describe, expect, it } from "vitest";
import { isTablesContribution } from "./dataSources";

describe("isTablesContribution", () => {
    it("accepts a tables envelope whose groups are an object map", () => {
        expect(
            isTablesContribution({
                kind: "tables",
                groups: { t: [["a", 1]] },
            }),
        ).toBe(true);
    });

    it("rejects null, array, and missing groups", () => {
        expect(isTablesContribution({ kind: "tables", groups: null })).toBe(
            false,
        );
        expect(isTablesContribution({ kind: "tables", groups: [] })).toBe(
            false,
        );
        expect(isTablesContribution({ kind: "tables" })).toBe(false);
        expect(isTablesContribution(null)).toBe(false);
    });
});
