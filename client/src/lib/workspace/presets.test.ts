import { describe, expect, it } from "vitest";
import { PRESET_ROWS } from "./presets";

describe("presets", () => {
    it("every preset covers its grid with no holes and no overlaps", () => {
        for (const row of PRESET_ROWS) {
            for (const p of row.presets) {
                expect(p.count, p.id).toBe(row.count);
                expect(p.cells, p.id).toHaveLength(p.count);
                const hits = Array<number>(p.cols.length * p.rows.length).fill(
                    0,
                );
                for (const c of p.cells) {
                    expect(c.col + c.colSpan, p.id).toBeLessThanOrEqual(
                        p.cols.length,
                    );
                    expect(c.row, p.id).toBeLessThan(p.rows.length);
                    for (let k = c.col; k < c.col + c.colSpan; k++) {
                        hits[c.row * p.cols.length + k]++;
                    }
                }
                expect(
                    hits.every((h) => h === 1),
                    p.id,
                ).toBe(true);
            }
        }
    });
});
