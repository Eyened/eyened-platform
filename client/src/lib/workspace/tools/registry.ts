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
    /** One line for the keys and gestures that have no button; empty when there are none. */
    hint: string;
}

export const TOOLS: readonly ToolDef[] = [
    {
        id: "zoom",
        name: "Zoom",
        key: "Z",
        group: "View",
        kind: "modal",
        icon: ZoomIn,
        hint: "Drag down zooms in, up zooms out",
    },
    {
        id: "pan",
        name: "Pan",
        key: "T",
        group: "View",
        kind: "modal",
        icon: Move,
        hint: "Drag pans · click centres there",
    },
    {
        id: "crosshair",
        name: "Cross-hair",
        key: "J",
        group: "View",
        kind: "modal",
        icon: CenterCircle,
        hint: "Click or drag sets the cross-hair",
    },
    {
        id: "reset",
        name: "Reset view",
        key: "Esc",
        group: "View",
        kind: "action",
        icon: ZoomReset,
        hint: "",
    },
    {
        id: "distance",
        name: "Distance",
        key: "D",
        group: "Measure",
        kind: "modal",
        icon: Ruler,
        hint: "",
    },
    {
        id: "circle",
        name: "ETDRS circle",
        key: "C",
        group: "Measure",
        kind: "modal",
        icon: CircleDash,
        hint: "",
    },
    {
        id: "brush",
        name: "Brush",
        key: "B",
        group: "Draw",
        kind: "modal",
        icon: PaintBrush,
        hint: "",
    },
    {
        id: "eraser",
        name: "Eraser",
        key: "E",
        group: "Draw",
        kind: "modal",
        icon: Erase,
        hint: "",
    },
    {
        id: "polygon",
        name: "Polygon",
        key: "L",
        group: "Draw",
        kind: "modal",
        icon: AreaCustom,
        hint: "",
    },
    {
        id: "enhance",
        name: "Enhance",
        key: null,
        group: "Draw",
        kind: "modal",
        icon: MagicWand,
        hint: "",
    },
    {
        id: "point",
        name: "Point",
        key: "P",
        group: "Place",
        kind: "modal",
        icon: Location,
        hint: "",
    },
    {
        id: "etdrs",
        name: "Place ETDRS grid",
        key: "G",
        group: "Place",
        kind: "modal",
        icon: Target,
        hint: "",
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

export const NO_TOOL_HINT =
    "Shift+drag pans · wheel steps slices · Shift+wheel zooms · hold H hides overlays";

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
