/** Per-user viewer panel state; each read and write survives private mode and quota errors. */

const LEFT_KEY = "eyened:viewer:leftPanel";
const RIGHT_KEY = "eyened:viewer:rightOpen";
const STRIP_KEY = "eyened:viewer:strip";

export type LeftPanel = "images" | "info" | "help";
const PANELS: readonly string[] = ["images", "info", "help"];

/** The open left panel; null for none, undefined when the user never chose. */
export function readLeftPanel(): LeftPanel | null | undefined {
    try {
        const raw = localStorage.getItem(LEFT_KEY);
        if (raw === "none") return null;
        return raw !== null && PANELS.includes(raw)
            ? (raw as LeftPanel)
            : undefined;
    } catch {
        return undefined;
    }
}

export function writeLeftPanel(panel: LeftPanel | null): void {
    try {
        localStorage.setItem(LEFT_KEY, panel ?? "none");
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}

/** Whether the right column is open; undefined when the user never chose. */
export function readRightOpen(): boolean | undefined {
    try {
        const raw = localStorage.getItem(RIGHT_KEY);
        if (raw === "true") return true;
        if (raw === "false") return false;
        return undefined;
    } catch {
        return undefined;
    }
}

export function writeRightOpen(open: boolean): void {
    try {
        localStorage.setItem(RIGHT_KEY, String(open));
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}

/** Whether the thumbnail strip is on in /view; undefined when the user never chose. */
export function readStripOn(): boolean | undefined {
    try {
        const raw = localStorage.getItem(STRIP_KEY);
        if (raw === "true") return true;
        if (raw === "false") return false;
        return undefined;
    } catch {
        return undefined;
    }
}

export function writeStripOn(on: boolean): void {
    try {
        localStorage.setItem(STRIP_KEY, String(on));
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}
