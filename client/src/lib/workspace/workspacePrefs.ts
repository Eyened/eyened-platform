/** Per-user viewer panel state; each read and write survives private mode and quota errors. */

import { MediaQuery } from "svelte/reactivity";
import type { LocalizerMode } from "./workspaceRules";

const LEFT_KEY = "eyened:viewer:leftPanel";
const RIGHT_KEY = "eyened:viewer:rightOpen";
const STRIP_KEY = "eyened:viewer:strip";
const TRACKING_KEY = "eyened:viewer:stripTracking";
const LOCALIZER_KEY = "eyened:viewer:stripLocalizer";

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

/** The strip's start value: off on a narrow window, else the task's config or the /view choice. */
export function startStripOn(taskStrip?: boolean): boolean {
    if (!new MediaQuery("min-width: 42rem").current) return false;
    return taskStrip ?? readStripOn() ?? true;
}

export function writeStripOn(on: boolean): void {
    try {
        localStorage.setItem(STRIP_KEY, String(on));
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}

/** Whether strip tiles follow the crosshair; on unless the user turned it off. */
export function readStripTracking(): boolean {
    try {
        return localStorage.getItem(TRACKING_KEY) !== "false";
    } catch {
        return true;
    }
}

export function writeStripTracking(on: boolean): void {
    try {
        localStorage.setItem(TRACKING_KEY, String(on));
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}

/** Which localizer lines strip tiles draw; All unless the user chose another. */
export function readStripLocalizer(): LocalizerMode {
    try {
        const raw = localStorage.getItem(LOCALIZER_KEY);
        return raw === "off" || raw === "current" ? raw : "all";
    } catch {
        return "all";
    }
}

export function writeStripLocalizer(mode: LocalizerMode): void {
    try {
        localStorage.setItem(LOCALIZER_KEY, mode);
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}
