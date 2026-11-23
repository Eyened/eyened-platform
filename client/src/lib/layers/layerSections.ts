/** Layers sections, in panel order. En-face projection and Localizer lines come with their own inputs. */
export type LayerSectionId =
    | "segmentations"
    | "etdrs"
    | "pointsets"
    | "distance";

/** The old panel name a task's `layout.hide` uses for each section. */
const HIDDEN_BY: Record<LayerSectionId, string> = {
    segmentations: "Segmentation",
    etdrs: "ETDRS",
    pointsets: "Registration",
    distance: "Measure",
};

const ORDER: readonly LayerSectionId[] = [
    "segmentations",
    "etdrs",
    "pointsets",
    "distance",
];

export interface LayerSectionsInput {
    is2D: boolean;
    hasEtdrsSchema: boolean;
    hasRegistrationSchema: boolean;
    /** The task's `layout.hide`. */
    hide: readonly string[];
}

/** The sections an image gets: today's panel rules, then the task's `layout.hide`. */
export function layerSections(input: LayerSectionsInput): LayerSectionId[] {
    const applies: Record<LayerSectionId, boolean> = {
        segmentations: true,
        etdrs: input.is2D && input.hasEtdrsSchema,
        pointsets: input.is2D && input.hasRegistrationSchema,
        distance: true,
    };
    return ORDER.filter(
        (id) => applies[id] && !input.hide.includes(HIDDEN_BY[id]),
    );
}
