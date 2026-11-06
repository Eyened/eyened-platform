import type { RenderMode, WindowLevel } from "./viewer-utils";

export type BarState = "full" | "compact" | "folded";

/** Content widths in px. `full` is null for types without stretch, which have no full state. */
export type BarWidths = { full: number | null; compact: number };

/** The largest bar state that fits. */
export function barState(widths: BarWidths, available: number): BarState {
    if (widths.full !== null && available >= widths.full) return "full";
    return available >= widths.compact ? "compact" : "folded";
}

export const STRETCH_PRESETS = [1, 2, 4, 8, 16];
const LOG_MIN = Math.log(0.3);
const LOG_STEP = 0.1;
/** The stretch slider runs over whole notches, 0.1 apart in log stretch from 0.3 to 20. */
export const STRETCH_NOTCHES = Math.round((Math.log(20) - LOG_MIN) / LOG_STEP);

export function stretchToNotch(stretch: number): number {
    const notch = Math.round((Math.log(stretch) - LOG_MIN) / LOG_STEP);
    return Math.max(0, Math.min(STRETCH_NOTCHES, notch));
}

export function notchToStretch(notch: number): number {
    return Math.exp(LOG_MIN + notch * LOG_STEP);
}

/** The preset `stretch` equals, or "" when it matches none. */
export function stretchPreset(stretch: number): string {
    const preset = STRETCH_PRESETS.find((p) => Math.abs(p - stretch) < 0.001);
    return preset === undefined ? "" : String(preset);
}

/** "8×", "3.5×". */
export function shortStretch(stretch: number): string {
    return `${Number(stretch.toFixed(1))}×`;
}

/** The folded bar's label: every setting that differs from its default, e.g. "CLAHE · 4×". */
export function nonDefaultLabel(view: {
    mode: RenderMode;
    windowLevel: WindowLevel;
    defaultWindowLevel: WindowLevel;
    stretch?: number;
    defaultStretch?: number;
}): string {
    const { windowLevel: wl, defaultWindowLevel: start } = view;
    const parts: string[] = [];
    if (view.mode !== "Original") parts.push(view.mode);
    if (wl.min !== start.min || wl.max !== start.max)
        parts.push(`W/L ${wl.min}–${wl.max}`);
    if (
        view.stretch !== undefined &&
        Math.abs(view.stretch - (view.defaultStretch ?? 0)) >= 0.001
    )
        parts.push(shortStretch(view.stretch));
    return parts.join(" · ");
}

/** Widths in px of the parts of the readout line. */
export type ReadoutWidths = {
    numbers: number;
    count: number;
    word: number;
    readout: number;
};

/** What the readout line shows: the count and the word drop first, then the number line. */
export function readoutParts(
    w: ReadoutWidths,
    available: number,
): { numbers: boolean; count: boolean; word: boolean } {
    const base = w.numbers + w.readout;
    if (base + w.word + w.count <= available)
        return { numbers: true, count: true, word: true };
    if (base <= available) return { numbers: true, count: false, word: false };
    return { numbers: false, count: false, word: true };
}
