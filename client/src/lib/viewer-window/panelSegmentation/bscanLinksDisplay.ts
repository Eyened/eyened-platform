export type BscanDisplayItem =
    | { kind: "link"; scanNr: number }
    | { kind: "ellipsis" };

/** Show every link when at most this many annotated B-scans exist. */
export const BSCAN_LINKS_SHOW_ALL_MAX = 12;

/** Half-width of the window around the current slice (in the sorted index list). */
const WINDOW_RADIUS = 4;

function indexAtOrBefore(sorted: number[], value: number): number {
    let pos = 0;
    for (let i = 0; i < sorted.length; i++) {
        if (sorted[i]! <= value) {
            pos = i;
        } else {
            break;
        }
    }
    return pos;
}

/**
 * Build B-scan link items for the panel: all links when few, otherwise a window
 * around the viewer's current index plus first/last with ellipsis.
 */
export function buildBscanDisplayItems(
    indices: number[],
    currentIndex: number,
): BscanDisplayItem[] {
    if (indices.length === 0) {
        return [];
    }

    const sorted = [...indices].sort((a, b) => a - b);
    if (sorted.length <= BSCAN_LINKS_SHOW_ALL_MAX) {
        return sorted.map((scanNr) => ({ kind: "link", scanNr }));
    }

    const exactPos = sorted.indexOf(currentIndex);
    const centerPos =
        exactPos >= 0 ? exactPos : indexAtOrBefore(sorted, currentIndex);

    const winStart = Math.max(0, centerPos - WINDOW_RADIUS);
    const winEnd = Math.min(sorted.length - 1, centerPos + WINDOW_RADIUS);

    const items: BscanDisplayItem[] = [];

    const pushEllipsis = () => {
        if (items.at(-1)?.kind !== "ellipsis") {
            items.push({ kind: "ellipsis" });
        }
    };

    if (winStart > 0) {
        items.push({ kind: "link", scanNr: sorted[0]! });
        if (winStart > 1) {
            pushEllipsis();
        }
    }

    for (let i = winStart; i <= winEnd; i++) {
        items.push({ kind: "link", scanNr: sorted[i]! });
    }

    if (winEnd < sorted.length - 1) {
        if (winEnd < sorted.length - 2) {
            pushEllipsis();
        }
        items.push({ kind: "link", scanNr: sorted[sorted.length - 1]! });
    }

    return items;
}
