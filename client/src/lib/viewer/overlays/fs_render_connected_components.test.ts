import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { colors } from "./colors";

const shader = readFileSync(
    resolve(import.meta.dirname, "./fs_render_connected_components.frag"),
    "utf8",
);

describe("connected-component color wrap", () => {
    it("declares a palette matching colors.ts and wraps labels into it", () => {
        expect(shader).toContain(`uniform vec3[${colors.length}] u_colors`);
        // Only `colors.length` entries are uploaded. Indexing % 256u leaves
        // labels 33–255 on unset (black) uniforms — the bottom of a busy mask.
        expect(shader).toMatch(
            new RegExp(
                String.raw`u_colors\[\(i - 1u\) % uint\(u_colors\.length\(\)\)\]`,
            ),
        );
    });
});
