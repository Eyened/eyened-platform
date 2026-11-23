/** How to display OCTA dual volumes in the B-scan viewer. */
export type AngioDisplayMode = "structural" | "flow" | "overlay";

export const ANGIO_DISPLAY_MODES: readonly AngioDisplayMode[] = [
    "structural",
    "flow",
    "overlay",
] as const;

export const ANGIO_DISPLAY_LABELS: Record<AngioDisplayMode, string> = {
    structural: "Structural OCT",
    flow: "Angio flow",
    overlay: "Flow overlay (red)",
};

/** GLSL `u_angio_mode`: 0 structural, 1 flow-only, 2 red overlay. */
export const ANGIO_MODE_UNIFORM: Record<AngioDisplayMode, number> = {
    structural: 0,
    flow: 1,
    overlay: 2,
};

export function angioModeUniform(mode: AngioDisplayMode): number {
    return ANGIO_MODE_UNIFORM[mode];
}
