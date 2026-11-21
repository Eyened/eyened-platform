/** Layers sections, in panel order. En-face projection and Localizer lines come with their own inputs. */
export type LayerSectionId =
    | "segmentations"
    | "etdrs"
    | "pointsets"
    | "blend"
    | "distance"
    | "projection"
    | "localizer";

/** The old panel name a task's `layout.hide` uses for each section. */
const HIDDEN_BY: Record<LayerSectionId, string | null> = {
    segmentations: "Segmentation",
    etdrs: "ETDRS",
    pointsets: "Registration",
    blend: "Registration",
    distance: "Measure",
    // The projection shows segmentation content, so blinding segmentations hides it too.
    projection: "Segmentation",
    localizer: null, // No old panel had it, so no layout.hide name hides it.
};

const ORDER: readonly LayerSectionId[] = [
    "segmentations",
    "etdrs",
    "pointsets",
    "blend",
    "distance",
    "projection",
    "localizer",
];

export interface LayerSectionsInput {
    is2D: boolean;
    hasEtdrsSchema: boolean;
    hasRegistrationSchema: boolean;
    /** The image is an OCT's `_proj` or links to a loaded OCT. */
    projection: boolean;
    /** The image is a loaded OCT's localizer. */
    localizer: boolean;
    /** The task's `layout.hide`. */
    hide: readonly string[];
}

/** The sections an image gets: today's panel rules, then the task's `layout.hide`. */
export function layerSections(input: LayerSectionsInput): LayerSectionId[] {
    const applies: Record<LayerSectionId, boolean> = {
        segmentations: true,
        etdrs: input.is2D && input.hasEtdrsSchema,
        pointsets: input.is2D && input.hasRegistrationSchema,
        blend: input.is2D && input.hasRegistrationSchema,
        distance: true,
        projection: input.projection,
        localizer: input.localizer,
    };
    return ORDER.filter((id) => {
        const hiddenBy = HIDDEN_BY[id];
        return applies[id] && !(hiddenBy && input.hide.includes(hiddenBy));
    });
}

/** The Layers panel tab a section sits in: objects in Layers, view settings in Display. */
export function tabOf(id: LayerSectionId): "layers" | "display" {
    return id === "blend" || id === "projection" || id === "localizer"
        ? "display"
        : "layers";
}
