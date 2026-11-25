import {
    GROUPS,
    KEYBOARD_CURSOR_KEYS,
    NO_TOOL_KEYS,
    TOOLS,
    type KeyRow,
    type ToolGroup,
    type ToolId,
} from "./tools/registry";

export interface HelpTool {
    name: string;
    /** null: "no key". */
    key: string | null;
    does: string;
    rows: readonly KeyRow[];
}

export interface HelpSection {
    title: string;
    tools: readonly HelpTool[];
    rows: readonly KeyRow[];
}

/** Keys the registry doesn't list: the viewport's other keys, the strip's and the Images list's, F1 and Esc. */
const PANEL_KEYS: readonly KeyRow[] = [
    { keys: "1 … 0", action: "Render mode: Original … Blue" },
    { keys: "M", action: "Magnifier on / off" },
    { keys: "⌘ / Ctrl+Z", action: "Undo" },
    { keys: "⌘ / Ctrl+Shift+Z, Ctrl+Y", action: "Redo" },
    {
        keys: "Page Up / Down",
        action: "Previous / next image in this viewport",
    },
    { keys: "Shift+Page Up / Down", action: "Previous / next page" },
    { keys: "← / →", action: "Move between thumbnails in the strip" },
    { keys: "↑ / ↓", action: "Move in the Images list" },
    {
        keys: "Enter",
        action: "Load the thumbnail or image into the selected viewport",
    },
    { keys: "F1", action: "Help" },
    { keys: "Esc", action: "Close Images, Info or Help" },
];

/** In the palette's order, then the keys that need no tool. */
export const HELP_SECTIONS: readonly HelpSection[] = [
    ...GROUPS.map((group) => ({
        title: group,
        tools: TOOLS.filter((t) => t.group === group).map((t) => ({
            name: t.name,
            key: t.key,
            does: t.does,
            rows: t.keys,
        })),
        rows: [],
    })),
    { title: "Viewport", tools: [], rows: NO_TOOL_KEYS },
    { title: "Images, layout and panels", tools: [], rows: PANEL_KEYS },
    { title: "Keyboard cursor", tools: [], rows: KEYBOARD_CURSOR_KEYS },
];

/** The sections with a match, keeping only matching rows, and how many key rows match. A tool's own key is a row; a tool's name and `does` match each of its rows. */
export function searchHelp(query: string): {
    sections: HelpSection[];
    count: number;
} {
    const q = query.trim().toLowerCase();
    const has = (...texts: string[]) =>
        texts.join(" ").toLowerCase().includes(q);
    let count = 0;
    const sections: HelpSection[] = [];
    for (const section of HELP_SECTIONS) {
        const tools: HelpTool[] = [];
        for (const tool of section.tools) {
            const own = has(tool.name, tool.does, tool.key ?? "no key");
            const rows = tool.rows.filter((r) =>
                has(tool.name, tool.does, r.keys, r.action),
            );
            if (!own && rows.length === 0) continue;
            count += (own ? 1 : 0) + rows.length;
            tools.push({ ...tool, rows });
        }
        const rows = section.rows.filter((r) => has(r.keys, r.action));
        count += rows.length;
        if (tools.length > 0 || rows.length > 0)
            sections.push({ title: section.title, tools, rows });
    }
    return { sections, count };
}

/** The section Help opens on: the armed tool's group; an armed form point field counts as Place. */
export function armedSection(
    armed: ToolId | null,
    pointFieldArmed: boolean,
): ToolGroup | null {
    if (pointFieldArmed) return "Place";
    return armed ? (TOOLS.find((t) => t.id === armed)?.group ?? null) : null;
}
