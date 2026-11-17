/** Per-user viewer panel state; each read and write survives private mode and quota errors. */

import { MediaQuery } from "svelte/reactivity";
import type { LocalizerMode } from "./workspaceRules";
import type { ToolMode } from "./tools/registry";
import type { LayerSectionId } from "$lib/layers/layerSections";

const LEFT_KEY = "eyened:viewer:leftPanel";
const RIGHT_KEY = "eyened:viewer:rightOpen";
const STRIP_KEY = "eyened:viewer:strip";
const TRACKING_KEY = "eyened:viewer:stripTracking";
const LOCALIZER_KEY = "eyened:viewer:stripLocalizer";
const TOOL_MODE_KEY = "eyened:viewer:toolMode";
const LAYER_AREA_KEY = "eyened:viewer:layerArea";
const LAYER_SECTIONS_KEY = "eyened:viewer:layerSections";

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

/** The palette's mode on /view; Browse unless the user chose All tools. */
export function readToolMode(): ToolMode {
    try {
        return localStorage.getItem(TOOL_MODE_KEY) === "all" ? "all" : "browse";
    } catch {
        return "browse";
    }
}

export function writeToolMode(mode: ToolMode): void {
    try {
        localStorage.setItem(TOOL_MODE_KEY, mode);
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}

/** Whether Layers shows each segmentation's area on this slice; on unless switched off. */
export function readLayerArea(): boolean {
    try {
        return localStorage.getItem(LAYER_AREA_KEY) !== "false";
    } catch {
        return true;
    }
}

export function writeLayerArea(on: boolean): void {
    try {
        localStorage.setItem(LAYER_AREA_KEY, String(on));
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}

/** The Layers sections open at the last visit; Segmentations only on the first. Distance lines always starts closed, since opening it arms the Measure tool. */
export function readLayerSections(): Record<LayerSectionId, boolean> {
    const open = {
        segmentations: true,
        etdrs: false,
        pointsets: false,
        distance: false,
    };
    try {
        const raw = localStorage.getItem(LAYER_SECTIONS_KEY);
        const stored: unknown = raw === null ? null : JSON.parse(raw);
        if (!Array.isArray(stored)) return open;
        for (const id of ["segmentations", "etdrs", "pointsets"] as const)
            open[id] = stored.includes(id);
        return open;
    } catch {
        return open;
    }
}

export function writeLayerSections(
    open: Record<LayerSectionId, boolean>,
): void {
    try {
        const ids = Object.keys(open).filter(
            (id) => open[id as LayerSectionId],
        );
        localStorage.setItem(LAYER_SECTIONS_KEY, JSON.stringify(ids));
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}
