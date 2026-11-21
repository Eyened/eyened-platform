/** Every palette tool once: the palette, ⋯, tooltips, keys, the options bar and Help read it. */

import AreaCustom from "carbon-icons-svelte/lib/AreaCustom.svelte";
import CenterCircle from "carbon-icons-svelte/lib/CenterCircle.svelte";
import CircleDash from "carbon-icons-svelte/lib/CircleDash.svelte";
import Erase from "carbon-icons-svelte/lib/Erase.svelte";
import Location from "carbon-icons-svelte/lib/Location.svelte";
import MagicWand from "carbon-icons-svelte/lib/MagicWand.svelte";
import Move from "carbon-icons-svelte/lib/Move.svelte";
import PaintBrush from "carbon-icons-svelte/lib/PaintBrush.svelte";
import Ruler from "carbon-icons-svelte/lib/Ruler.svelte";
import Target from "carbon-icons-svelte/lib/Target.svelte";
import ZoomIn from "carbon-icons-svelte/lib/ZoomIn.svelte";
import ZoomReset from "carbon-icons-svelte/lib/ZoomReset.svelte";
import type { Component } from "svelte";

/** One row of the Keys popover: a key or gesture, then what it does. */
export interface KeyRow {
    keys: string;
    action: string;
}

export type ToolId =
    | "zoom"
    | "pan"
    | "crosshair"
    | "reset"
    | "distance"
    | "circle"
    | "brush"
    | "eraser"
    | "polygon"
    | "enhance"
    | "point"
    | "etdrs";

export type ToolGroup = "View" | "Measure" | "Draw" | "Place";

export type ToolMode = "browse" | "all";

export interface ToolDef {
    id: ToolId;
    name: string;
    /** Shown in tooltips and menu rows; null for a tool without a key. */
    key: string | null;
    group: ToolGroup;
    /** A modal tool stays armed; an action runs once. */
    kind: "modal" | "action";
    icon: Component;
    /** The tooltip's second line: what the tool does. */
    does: string;
    /** The Keys popover's rows for keys and gestures that have no button; empty when there are none. */
    keys: readonly KeyRow[];
}

export const TOOLS: readonly ToolDef[] = [
    {
        id: "zoom",
        name: "Zoom",
        key: "Z",
        group: "View",
        kind: "modal",
        icon: ZoomIn,
        does: "Drag to zoom in or out",
        keys: [{ keys: "Drag down / up", action: "Zoom in / out" }],
    },
    {
        id: "pan",
        name: "Pan",
        key: "T",
        group: "View",
        kind: "modal",
        icon: Move,
        does: "Drag to move the image",
        keys: [
            { keys: "Drag", action: "Pan" },
            { keys: "Click", action: "Centre there" },
        ],
    },
    {
        id: "crosshair",
        name: "Cross-hair",
        key: "J",
        group: "View",
        kind: "modal",
        icon: CenterCircle,
        does: "Click or drag sets the cross-hair in linked viewports",
        keys: [{ keys: "Click or drag", action: "Set the cross-hair" }],
    },
    {
        id: "reset",
        name: "Reset view",
        key: "Esc",
        group: "View",
        kind: "action",
        icon: ZoomReset,
        does: "Fits the image again and clears this image's distance lines",
        keys: [],
    },
    {
        id: "distance",
        name: "Distance",
        key: "D",
        group: "Measure",
        kind: "modal",
        icon: Ruler,
        does: "Measures a straight line",
        keys: [
            { keys: "Click, then click", action: "Start, then end of a line" },
            { keys: "Drag an end", action: "Move it" },
            { keys: "Del", action: "Remove the line under the pointer" },
            { keys: "Esc", action: "Clear this image's lines" },
        ],
    },
    {
        id: "circle",
        name: "ETDRS circle",
        key: "C",
        group: "Measure",
        kind: "modal",
        icon: CircleDash,
        does: "Shows an ETDRS circle at the pointer in every viewport of this eye",
        keys: [{ keys: "[ / ]", action: "Previous / next size" }],
    },
    {
        id: "brush",
        name: "Brush",
        key: "B",
        group: "Draw",
        kind: "modal",
        icon: PaintBrush,
        does: "Paints into the selected segmentation",
        keys: [
            { keys: "Hold Space", action: "Paint" },
            { keys: "X", action: "Switch to Eraser" },
            { keys: "I", action: "Pick the feature under the pointer" },
        ],
    },
    {
        id: "eraser",
        name: "Eraser",
        key: "E",
        group: "Draw",
        kind: "modal",
        icon: Erase,
        does: "Removes paint from the selected segmentation",
        keys: [
            { keys: "Hold Space", action: "Erase" },
            { keys: "X", action: "Switch to Brush" },
            { keys: "I", action: "Pick the feature under the pointer" },
        ],
    },
    {
        id: "polygon",
        name: "Polygon",
        key: "L",
        group: "Draw",
        kind: "modal",
        icon: AreaCustom,
        does: "Fills or erases an outlined area",
        keys: [
            { keys: "Drag round an area", action: "Fill or erase it" },
            { keys: "Esc", action: "Cancel" },
        ],
    },
    {
        id: "enhance",
        name: "Enhance",
        key: null,
        group: "Draw",
        kind: "modal",
        icon: MagicWand,
        does: "Raises or lowers values in the selected probability segmentation",
        keys: [
            { keys: "Hold Space", action: "Enhance" },
            { keys: "X", action: "Switch increase / decrease" },
        ],
    },
    // ASSUMPTION: one key text for every platform, as the ⌘Z / Ctrl+Z shortcuts do.
    {
        id: "point",
        name: "Point",
        key: "P",
        group: "Place",
        kind: "modal",
        icon: Location,
        does: "Places matching points of the selected pointset",
        keys: [
            { keys: "Click", action: "Place a point" },
            { keys: "Drag a point", action: "Move it" },
            { keys: "Click a point", action: "Cycle its grade" },
            { keys: "⌘ / Ctrl-click", action: "Place on top of a point" },
            { keys: "[ / ]", action: "Previous / next point" },
        ],
    },
    {
        id: "etdrs",
        name: "Place ETDRS grid",
        key: "G",
        group: "Place",
        kind: "modal",
        icon: Target,
        does: "Places the selected grid's fovea and disc edge",
        keys: [
            { keys: "Click", action: "Place the selected point" },
            {
                keys: "Hold Space",
                action: "Place the selected point and follow the pointer",
            },
            { keys: "[ / ]", action: "Fovea / Disc edge" },
            { keys: "Del", action: "Remove the point under the pointer" },
        ],
    },
];

export const GROUPS: readonly ToolGroup[] = [
    "View",
    "Measure",
    "Draw",
    "Place",
];

/** Browse, the /view default: the view tools and Distance; the rest sit under ⋯. */
export const BROWSE: readonly ToolId[] = [
    "zoom",
    "pan",
    "crosshair",
    "reset",
    "distance",
];

/** Keys that work with no tool armed. */
export const NO_TOOL_KEYS: readonly KeyRow[] = [
    { keys: "Shift+drag", action: "Pan" },
    { keys: "Wheel", action: "Step slices" },
    { keys: "Shift+wheel", action: "Zoom" },
    { keys: "Enter", action: "Keyboard cursor" },
    { keys: "Hold H", action: "Hide overlays" },
    { keys: "O", action: "Localizer lines" },
];

/** Listed in place of the tool's keys while the keyboard cursor is on. */
export const KEYBOARD_CURSOR_KEYS: readonly KeyRow[] = [
    { keys: "Arrows", action: "Move" },
    { keys: "Shift+arrows", action: "Move 10 px" },
    { keys: "Space", action: "Click" },
    { keys: "Hold Space + arrows", action: "Drag" },
    { keys: "Esc", action: "Leave" },
];

export function toolById(id: ToolId): ToolDef {
    return TOOLS.find((t) => t.id === id)!;
}

/** The modal tool a letter arms, whatever its case. */
export function toolForKey(key: string): ToolDef | undefined {
    const k = key.toUpperCase();
    return TOOLS.find((t) => t.kind === "modal" && t.key === k);
}

export function offered(id: ToolId, mode: ToolMode): boolean {
    return mode === "all" || BROWSE.includes(id);
}
