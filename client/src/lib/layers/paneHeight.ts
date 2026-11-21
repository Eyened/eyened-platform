/** The pane's smallest height: its header and one line of its body. */
export const PANE_MIN_PX = 80;
/** The list keeps at least this much above the pane. */
export const LIST_MIN_PX = 96;
/** One arrow-key step of the pane's splitter. */
export const PANE_STEP_PX = 16;

/** The height a user set, within what the tab allows; null keeps the fit-content default. */
export function paneHeight(saved: number | null, tab: number): number | null {
    if (saved === null) return null;
    const max = Math.max(PANE_MIN_PX, tab - LIST_MIN_PX);
    return Math.min(Math.max(saved, PANE_MIN_PX), max);
}
