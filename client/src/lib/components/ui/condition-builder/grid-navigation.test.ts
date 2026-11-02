import { describe, expect, it } from "vitest";
import { move, rowCells } from "./grid-navigation";
import type { BuilderProperty } from "./types";

const PROPERTIES: BuilderProperty[] = [
    {
        id: "Laterality",
        label: "Laterality",
        options: ["L", "R"],
        operators: [
            { id: "oneOf", label: "is one of", value: "list" },
            { id: "isEmpty", label: "is empty", value: "none" },
        ],
    },
];

// Row 0 has a value; row 1 is "is empty" (no value part) and is the last row (add).
const grid = [
    rowCells(
        { id: 1, property: "Laterality", operator: "oneOf", value: ["L"] },
        PROPERTIES,
        false,
    ),
    rowCells(
        { id: 2, property: "Laterality", operator: "isEmpty" },
        PROPERTIES,
        true,
    ),
];

describe("condition grid", () => {
    it("lists the parts a row has, and add only on the last row", () => {
        expect(grid).toEqual([
            ["property", "operator", "value", "delete"],
            ["property", "operator", "delete", "add"],
        ]);
    });

    it("moves left and right through every cell, past the connectors, stopping at the ends", () => {
        expect(move(grid, { row: 0, cell: "delete" }, "ArrowRight")).toEqual({
            row: 1,
            cell: "property",
        });
        expect(move(grid, { row: 1, cell: "property" }, "ArrowLeft")).toEqual({
            row: 0,
            cell: "delete",
        });
        expect(
            move(grid, { row: 0, cell: "property" }, "ArrowLeft"),
        ).toBeNull();
        expect(move(grid, { row: 1, cell: "add" }, "ArrowRight")).toBeNull();
    });

    it("moves up and down to the same part, only if that row has it", () => {
        expect(move(grid, { row: 0, cell: "operator" }, "ArrowDown")).toEqual({
            row: 1,
            cell: "operator",
        });
        expect(move(grid, { row: 0, cell: "value" }, "ArrowDown")).toBeNull();
        expect(move(grid, { row: 1, cell: "add" }, "ArrowUp")).toBeNull();
        expect(move(grid, { row: 0, cell: "property" }, "ArrowUp")).toBeNull();
    });
});
