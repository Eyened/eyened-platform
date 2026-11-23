import type { Preset } from "./presets";

export type ArrangeOrder = "opened" | "visit" | "eye" | "modality";
export const ARRANGE_ORDERS: readonly ArrangeOrder[] = [
    "opened",
    "visit",
    "eye",
    "modality",
];

/** An open image with the keys Arrange sorts on. */
export interface CatalogueEntry {
    imageId: string;
    /** ASSUMPTION: the patient identifier, compared as a string (plan decision 14). */
    patient: string;
    /** Visit (study) date, yyyy-mm-dd, so string order is date order. */
    date: string;
    modalityRank: number;
    eyeRank: number;
}

/** A viewport slot. `id` is a render key that travels with the slot's contents on a swap or a preset change. */
export interface Slot {
    id: number;
    imageId: string | null;
}

// ASSUMPTION: this fixed modality order stands in for BIR's "series"; sub-project 6 may refine it.
export function modalityRank(
    modality?: string | null,
    field?: string | null,
): number {
    if (modality === "ColorFundus") {
        if (field === "F1") return 0;
        if (field === "F2") return 1;
        return 5;
    }
    if (modality === "InfraredReflectance") return 2;
    if (modality === "Autofluorescence") return 3;
    if (modality === "OCT") return 4;
    return 5;
}

/** OD before OS. */
export function eyeRank(laterality?: string | null): number {
    if (laterality === "R") return 0;
    if (laterality === "L") return 1;
    return 2;
}

const SORT_KEYS: Record<ArrangeOrder, (keyof CatalogueEntry)[]> = {
    visit: ["patient", "date", "modalityRank", "eyeRank"],
    eye: ["patient", "eyeRank", "modalityRank", "date"],
    modality: ["patient", "modalityRank", "date", "eyeRank"],
    // No keys: the stable sort keeps the order the images were opened in.
    opened: [],
};

/** Stable, so ties keep the input order; Workspace passes the opened order. */
export function sortCatalogue(
    entries: readonly CatalogueEntry[],
    order: ArrangeOrder,
): CatalogueEntry[] {
    const keys = SORT_KEYS[order];
    return [...entries].sort((a, b) => {
        for (const key of keys) {
            if (a[key] < b[key]) return -1;
            if (a[key] > b[key]) return 1;
        }
        return 0;
    });
}

/** ⌈images / slots⌉ pages, at least one. */
export function pageCount(images: number, slots: number): number {
    return Math.max(1, Math.ceil(images / slots));
}

/** Page k fills the n slots, in slot order, with catalogue images (k−1)·n+1 to k·n. */
export function fillPage(
    slots: readonly Slot[],
    catalogue: readonly string[],
    page: number,
): Slot[] {
    const first = (page - 1) * slots.length;
    return slots.map((slot, i) => ({
        id: slot.id,
        imageId: catalogue[first + i] ?? null,
    }));
}

/** The 1-based page an image is on with n slots; page 1 when it isn't in the catalogue. */
export function pageOf(
    catalogue: readonly string[],
    slots: number,
    imageId: string | null,
): number {
    const i = imageId ? catalogue.indexOf(imageId) : -1;
    return i < 0 ? 1 : Math.floor(i / slots) + 1;
}

/** The two slots trade contents and render keys. */
export function swapSlots(
    slots: readonly Slot[],
    a: number,
    b: number,
): Slot[] {
    const next = [...slots];
    [next[a], next[b]] = [next[b], next[a]];
    return next;
}

export function pruneSlots(
    slots: readonly Slot[],
    keep: (imageId: string) => boolean,
): { slots: Slot[]; emptied: number } {
    let emptied = 0;
    const next = slots.map((slot) => {
        if (slot.imageId === null || keep(slot.imageId)) return slot;
        emptied++;
        return { id: slot.id, imageId: null };
    });
    return { slots: next, emptied };
}

export interface PresetChange {
    slots: Slot[];
    page: number;
    selected: number;
}

/**
 * The page becomes the one holding the old page's first image. The selection follows its image, else slot 1.
 * A new slot reuses the render key of an old slot that showed the same image, so its view survives.
 */
export function changePreset(input: {
    slots: readonly Slot[];
    selected: number;
    catalogue: readonly string[];
    preset: Preset;
    newId: () => number;
}): PresetChange {
    const { slots, catalogue, preset, newId } = input;
    const anchor = slots.find((slot) => slot.imageId !== null)?.imageId ?? null;
    const selectedImage = slots[input.selected]?.imageId ?? null;

    const page = pageOf(catalogue, preset.count, anchor);
    const empty: Slot[] = preset.cells.map(() => ({ id: -1, imageId: null }));
    const used = new Set<number>();
    const next = fillPage(empty, catalogue, page).map((slot) => {
        const match = slots.find(
            (old) =>
                old.imageId !== null &&
                old.imageId === slot.imageId &&
                !used.has(old.id),
        );
        const id = match ? match.id : newId();
        used.add(id);
        return { id, imageId: slot.imageId };
    });

    const selected = selectedImage
        ? Math.max(
              0,
              next.findIndex((slot) => slot.imageId === selectedImage),
          )
        : 0;
    return { slots: next, page, selected };
}

/** Previous / Next FrameSet: the neighbouring image of the same visit, in By-visit order; null at the visit's ends. */
export function frameSetNeighbour(
    entries: readonly CatalogueEntry[],
    imageId: string,
    delta: 1 | -1,
): string | null {
    const byVisit = sortCatalogue(entries, "visit");
    const i = byVisit.findIndex((e) => e.imageId === imageId);
    if (i < 0) return null;
    const next = byVisit[i + delta];
    const here = byVisit[i];
    return next && next.patient === here.patient && next.date === here.date
        ? next.imageId
        : null;
}

export type Axis = "col" | "row";

/** Minimum viewport size a splitter may leave, in CSS px: width for column splitters, height for row splitters. */
export const MIN_VIEWPORT: Record<Axis, number> = { col: 160, row: 120 };

/** Gap between viewports, in CSS px. */
export const GRID_GAP = 2;

/** One splitter: the boundary between tracks `line − 1` and `line`, running along the other axis's tracks [from, to). */
export interface SplitterSegment {
    axis: Axis;
    line: number;
    from: number;
    to: number;
}

function spanOf(cell: Preset["cells"][number], axis: Axis): [number, number] {
    return axis === "col"
        ? [cell.col, cell.col + cell.colSpan]
        : [cell.row, cell.row + 1];
}

/** Splitters run along every internal track line and stop where a cell spans across the line. */
export function splitterSegments(preset: Preset): SplitterSegment[] {
    const out: SplitterSegment[] = [];
    for (const axis of ["col", "row"] as const) {
        const other: Axis = axis === "col" ? "row" : "col";
        const tracks = axis === "col" ? preset.cols.length : preset.rows.length;
        const along = axis === "col" ? preset.rows.length : preset.cols.length;
        for (let line = 1; line < tracks; line++) {
            const crossed = Array<boolean>(along).fill(false);
            for (const cell of preset.cells) {
                const [s, e] = spanOf(cell, axis);
                if (s < line && line < e) {
                    const [os, oe] = spanOf(cell, other);
                    for (let k = os; k < oe; k++) crossed[k] = true;
                }
            }
            let from = -1;
            for (let k = 0; k <= along; k++) {
                const open = k < along && !crossed[k];
                if (open && from < 0) from = k;
                if (!open && from >= 0) {
                    out.push({ axis, line, from, to: k });
                    from = -1;
                }
            }
        }
    }
    return out;
}

/** px per fr along one axis, gaps excluded. */
export function pxPerFr(sizes: readonly number[], lengthPx: number): number {
    const total = sizes.reduce((a, b) => a + b, 0);
    return Math.max(0, lengthPx - GRID_GAP * (sizes.length - 1)) / total;
}

/**
 * The range (fr) for track a = line − 1, keeping every viewport at least MIN_VIEWPORT; track b = line takes the rest of their sum.
 * A range the viewports already violate never gets worse; an impossible one holds the splitter where it is.
 */
export function splitRange(
    preset: Preset,
    sizes: readonly number[],
    axis: Axis,
    line: number,
    lengthPx: number,
): { lo: number; hi: number; total: number; perFr: number } {
    const a = line - 1;
    const b = line;
    const total = sizes[a] + sizes[b];
    const perFr = pxPerFr(sizes, lengthPx);
    const minFr = perFr > 0 ? MIN_VIEWPORT[axis] / perFr : Infinity;
    let lo = 0;
    let hi = total;
    for (const cell of preset.cells) {
        const [s, e] = spanOf(cell, axis);
        const hasA = s <= a && a < e;
        const hasB = s <= b && b < e;
        if (hasA === hasB) continue;
        let rest = 0;
        for (let t = s; t < e; t++) if (t !== a && t !== b) rest += sizes[t];
        if (hasA) lo = Math.max(lo, minFr - rest);
        else hi = Math.min(hi, total - (minFr - rest));
    }
    const current = sizes[a];
    if (lo > hi) return { lo: current, hi: current, total, perFr };
    return {
        lo: Math.min(lo, current),
        hi: Math.max(hi, current),
        total,
        perFr,
    };
}

/** Sets track line − 1 to `a` fr and gives track `line` the rest of their sum. */
export function setSplit(
    sizes: readonly number[],
    line: number,
    a: number,
): number[] {
    const next = [...sizes];
    const total = sizes[line - 1] + sizes[line];
    next[line - 1] = a;
    next[line] = total - a;
    return next;
}

/** Which localizer lines strip tiles draw. */
export type LocalizerMode = "off" | "current" | "all";
