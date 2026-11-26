/** Per-user viewer panel state; each read and write survives private mode and quota errors. */

import { MediaQuery } from "svelte/reactivity";
import {
    MAGNIFIER_CORNERS,
    MAGNIFIER_DEFAULTS,
    MAGNIFIER_SIZES,
    MAGNIFIER_ZOOMS,
    type MagnifierPrefs,
    type MagnifierSize,
} from "./magnifier";
import { PAINT_DEFAULTS, SIZE_MAX, SIZE_MIN, type PaintPrefs } from "./paint";
import { RIGHT_MIN_PX } from "./rightWidth";
import type { LocalizerMode } from "./workspaceRules";
import type { ToolMode } from "./tools/registry";
import type { LayerSectionId } from "$lib/layers/layerSections";

const LEFT_KEY = "eyened:viewer:leftPanel";
const RIGHT_KEY = "eyened:viewer:rightOpen";
const RIGHT_WIDTH_KEY = "eyened:viewer:rightWidth";
const STRIP_KEY = "eyened:viewer:strip";
const TRACKING_KEY = "eyened:viewer:stripTracking";
const LOCALIZER_KEY = "eyened:viewer:localizer";
const TOOL_MODE_KEY = "eyened:viewer:toolMode";
const LAYER_AREA_KEY = "eyened:viewer:layerArea";
const LAYER_SECTIONS_KEY = "eyened:viewer:layerSections";
const PANE_HEIGHT_KEY = "eyened:viewer:paneHeight";
const MAGNIFIER_KEY = "eyened:viewer:magnifier";
const PAINT_KEY = "eyened:viewer:paint";
const LAST_FORM_KEY = "eyened:viewer:lastFormSchema";

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

/** The open right column's width the user set, in px; 288 when none or bad. */
export function readRightWidth(): number {
    try {
        const raw = localStorage.getItem(RIGHT_WIDTH_KEY);
        const px = raw === null ? NaN : Number(raw);
        return Number.isFinite(px) && px > 0 ? px : RIGHT_MIN_PX;
    } catch {
        return RIGHT_MIN_PX;
    }
}

export function writeRightWidth(px: number): void {
    try {
        localStorage.setItem(RIGHT_WIDTH_KEY, String(Math.round(px)));
    } catch {
        // Private mode or quota: the width lasts this session only.
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

/** The localizer lines mode a viewport starts on: the browser's last choice, Off when none. */
export function readLocalizer(): LocalizerMode {
    try {
        const raw = localStorage.getItem(LOCALIZER_KEY);
        return raw === "current" || raw === "all" ? raw : "off";
    } catch {
        return "off";
    }
}

export function writeLocalizer(mode: LocalizerMode): void {
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

/** The schema Add form made last; null when none or storage fails. */
export function readLastFormSchema(): number | null {
    try {
        const raw = localStorage.getItem(LAST_FORM_KEY);
        const id = raw === null ? NaN : Number(raw);
        return Number.isInteger(id) ? id : null;
    } catch {
        return null;
    }
}

export function writeLastFormSchema(id: number): void {
    try {
        localStorage.setItem(LAST_FORM_KEY, String(id));
    } catch {
        // Private mode or quota: the next page starts on the first form.
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

/** The Layers sections open at the last visit; Segmentations only on the first. */
export function readLayerSections(): Record<LayerSectionId, boolean> {
    const open = {
        segmentations: true,
        etdrs: false,
        pointsets: false,
        registration: false,
        blend: false,
        distance: false,
        projection: false,
        localizer: false,
    };
    try {
        const raw = localStorage.getItem(LAYER_SECTIONS_KEY);
        const stored: unknown = raw === null ? null : JSON.parse(raw);
        if (!Array.isArray(stored)) return open;
        for (const id of [
            "segmentations",
            "etdrs",
            "pointsets",
            "registration",
            "blend",
            "distance",
            "projection",
            "localizer",
        ] as const)
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

/** The Selected pane height the user set, in px; null keeps the fit-content default. */
export function readPaneHeight(): number | null {
    try {
        const raw = localStorage.getItem(PANE_HEIGHT_KEY);
        const px = raw === null ? NaN : Number(raw);
        return Number.isFinite(px) && px > 0 ? px : null;
    } catch {
        return null;
    }
}

export function writePaneHeight(px: number | null): void {
    try {
        if (px === null) localStorage.removeItem(PANE_HEIGHT_KEY);
        else localStorage.setItem(PANE_HEIGHT_KEY, String(Math.round(px)));
    } catch {
        // Private mode or quota: the height lasts this session only.
    }
}

/** The Magnifier's last settings; a missing or unknown field takes its default. */
export function readMagnifier(): MagnifierPrefs {
    try {
        const raw = localStorage.getItem(MAGNIFIER_KEY);
        const stored: unknown = raw === null ? null : JSON.parse(raw);
        if (typeof stored !== "object" || stored === null)
            return { ...MAGNIFIER_DEFAULTS };
        const s = stored as Record<string, unknown>;
        const place = (v: unknown) =>
            typeof v === "number" && Number.isFinite(v) ? v : null;
        return {
            on: s.on === true,
            zoom:
                MAGNIFIER_ZOOMS.find((z) => z === s.zoom) ??
                MAGNIFIER_DEFAULTS.zoom,
            size:
                typeof s.size === "string" &&
                Object.hasOwn(MAGNIFIER_SIZES, s.size)
                    ? (s.size as MagnifierSize)
                    : MAGNIFIER_DEFAULTS.size,
            corner:
                MAGNIFIER_CORNERS.find((c) => c === s.corner) ??
                MAGNIFIER_DEFAULTS.corner,
            x: place(s.x),
            y: place(s.y),
        };
    } catch {
        return { ...MAGNIFIER_DEFAULTS };
    }
}

export function writeMagnifier(m: MagnifierPrefs): void {
    try {
        localStorage.setItem(MAGNIFIER_KEY, JSON.stringify(m));
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}

/** The last paint settings; a missing, non-numeric or out-of-range field takes its default. */
export function readPaint(): PaintPrefs {
    try {
        const raw = localStorage.getItem(PAINT_KEY);
        const stored: unknown = raw === null ? null : JSON.parse(raw);
        if (typeof stored !== "object" || stored === null)
            return { ...PAINT_DEFAULTS };
        const s = stored as Record<string, unknown>;
        const pick = (key: keyof PaintPrefs, min: number, max: number) => {
            const v = s[key];
            return typeof v === "number" && v >= min && v <= max
                ? v
                : PAINT_DEFAULTS[key];
        };
        return {
            size2D: pick("size2D", SIZE_MIN, SIZE_MAX),
            sizeBscan: pick("sizeBscan", SIZE_MIN, SIZE_MAX),
            hardness: pick("hardness", 0, 1),
            pressure: pick("pressure", 0, 1),
        };
    } catch {
        return { ...PAINT_DEFAULTS };
    }
}

export function writePaint(p: PaintPrefs): void {
    try {
        localStorage.setItem(PAINT_KEY, JSON.stringify(p));
    } catch {
        // Private mode or quota: the choice lasts this session only.
    }
}
