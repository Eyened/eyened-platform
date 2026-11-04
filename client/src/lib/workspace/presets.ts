/** One viewport cell, in 0-based track indices. A cell spans columns only. */
export interface PresetCell {
    col: number;
    row: number;
    colSpan: number;
}

export interface Preset {
    id: string;
    /** Accessible name of the preset button. */
    label: string;
    count: number;
    /** Initial track sizes, as fr weights. */
    cols: readonly number[];
    rows: readonly number[];
    /** Cells in slot order. */
    cells: readonly PresetCell[];
}

const cell = (col: number, row: number, colSpan = 1): PresetCell => ({
    col,
    row,
    colSpan,
});

const ones = (n: number): number[] => Array<number>(n).fill(1);

function grid(cols: number, rows: number, label: string): Preset {
    const cells: PresetCell[] = [];
    for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) cells.push(cell(col, row));
    }
    return {
        id: `${cols}x${rows}`,
        label,
        count: cols * rows,
        cols: ones(cols),
        rows: ones(rows),
        cells,
    };
}

// ASSUMPTION: the fewest tracks that give equal widths in each row (plan decision 10).
const THREE_ABOVE_TWO: Preset = {
    id: "3+2",
    label: "3 above 2",
    count: 5,
    cols: [2, 1, 1, 2],
    rows: [1, 1],
    cells: [
        cell(0, 0),
        cell(1, 0, 2),
        cell(3, 0),
        cell(0, 1, 2),
        cell(2, 1, 2),
    ],
};

const FOUR_ABOVE_THREE: Preset = {
    id: "4+3",
    label: "4 above 3",
    count: 7,
    cols: [3, 1, 2, 2, 1, 3],
    rows: [1, 1],
    cells: [
        cell(0, 0),
        cell(1, 0, 2),
        cell(3, 0, 2),
        cell(5, 0),
        cell(0, 1, 2),
        cell(2, 1, 2),
        cell(4, 1, 2),
    ],
};

/** The Layout popover's rows. */
export const PRESET_ROWS: readonly {
    count: number;
    presets: readonly Preset[];
}[] = [
    { count: 1, presets: [grid(1, 1, "One viewport")] },
    {
        count: 2,
        presets: [grid(2, 1, "2 side by side"), grid(1, 2, "2 stacked")],
    },
    { count: 3, presets: [grid(3, 1, "3 side by side")] },
    { count: 4, presets: [grid(2, 2, "2 by 2"), grid(4, 1, "4 side by side")] },
    { count: 5, presets: [THREE_ABOVE_TWO] },
    { count: 6, presets: [grid(3, 2, "3 by 2"), grid(2, 3, "2 by 3")] },
    { count: 7, presets: [FOUR_ABOVE_THREE] },
    { count: 8, presets: [grid(4, 2, "4 by 2")] },
    { count: 9, presets: [grid(3, 3, "3 by 3")] },
    { count: 10, presets: [grid(5, 2, "5 by 2")] },
    { count: 12, presets: [grid(4, 3, "4 by 3"), grid(6, 2, "6 by 2")] },
    { count: 14, presets: [grid(7, 2, "7 by 2")] },
    { count: 16, presets: [grid(4, 4, "4 by 4")] },
];

const BY_ID = new Map(
    PRESET_ROWS.flatMap((row) => row.presets).map((p) => [p.id, p]),
);

export const DEFAULT_PRESET_ID = "1x1";

export function getPreset(id: string): Preset | undefined {
    return BY_ID.get(id);
}

/** The smallest row that holds n viewports; row 16 above that. */
export function smallestRowFor(n: number): (typeof PRESET_ROWS)[number] {
    return (
        PRESET_ROWS.find((r) => r.count >= n) ??
        PRESET_ROWS[PRESET_ROWS.length - 1]
    );
}
