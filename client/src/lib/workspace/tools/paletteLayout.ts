import {
    BROWSE,
    GROUPS,
    TOOLS,
    type ToolDef,
    type ToolGroup,
    type ToolMode,
} from "./registry";

export const SLOT_PX = 40;
export const GAP_PX = 12;

/** A run of slots between two gaps: one job's tools, or ⋯ More tools. */
export interface Section {
    group: ToolGroup | "More";
    tools: ToolDef[];
}

/** The mode's tools by job, packed in registry order; ⋯ comes last outside All tools. */
export function paletteSections(mode: ToolMode): Section[] {
    const sections: Section[] = GROUPS.map((group) => ({
        group,
        tools: TOOLS.filter(
            (t) =>
                t.group === group && (mode === "all" || BROWSE.includes(t.id)),
        ),
    })).filter((s) => s.tools.length > 0);
    if (mode !== "all") sections.push({ group: "More", tools: [] });
    return sections;
}

/** Height the flat palette needs: a slot per tool (⋯ is one) and a gap between sections. */
export function flatHeight(sections: Section[]): number {
    const slots = sections.reduce((n, s) => n + Math.max(s.tools.length, 1), 0);
    return slots * SLOT_PX + (sections.length - 1) * GAP_PX;
}

/** Two layouts, one threshold: flat while every slot fits, else one slot per job. */
export function paletteLayout(
    available: number,
    sections: Section[],
): "flat" | "flyout" {
    return available >= flatHeight(sections) ? "flat" : "flyout";
}
