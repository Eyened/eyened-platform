import type { BuilderProperty, BuilderRow } from "./types.js";

/** A condition row's focusable parts, in order. The "if"/"and" connector is never focusable. */
export type Cell = "property" | "operator" | "value" | "delete" | "add";
export type Position = { row: number; cell: Cell };

/** A row's parts: operator once there is a property, value once the operator takes one. */
export function rowCells(
    row: BuilderRow,
    properties: BuilderProperty[],
    last: boolean,
): Cell[] {
    const property = properties.find((p) => p.id === row.property);
    const operator = property?.operators.find((o) => o.id === row.operator);
    const cells: Cell[] = ["property"];
    if (property) cells.push("operator");
    if (operator && operator.value !== "none") cells.push("value");
    cells.push("delete");
    if (last) cells.push("add");
    return cells;
}

/**
 * Where an arrow key moves focus in the grid (IBM Products ConditionBuilder, Non-Hierarchical),
 * or null to stay: ←/→ step through every cell in reading order and stop at the ends;
 * ↑/↓ go to the same part in the next row, if it has one.
 */
export function move(
    grid: Cell[][],
    from: Position,
    key: string,
): Position | null {
    if (key === "ArrowLeft" || key === "ArrowRight") {
        const flat = grid.flatMap((cells, row) =>
            cells.map((cell) => ({ row, cell })),
        );
        const i = flat.findIndex(
            (p) => p.row === from.row && p.cell === from.cell,
        );
        const next = flat[i + (key === "ArrowRight" ? 1 : -1)];
        return i === -1 || !next ? null : next;
    }
    if (key === "ArrowUp" || key === "ArrowDown") {
        const row = from.row + (key === "ArrowDown" ? 1 : -1);
        return grid[row]?.includes(from.cell) ? { row, cell: from.cell } : null;
    }
    return null;
}
