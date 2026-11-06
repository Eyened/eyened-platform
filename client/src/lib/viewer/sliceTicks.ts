/** A click this close to a tick goes to its slice. */
const TICK_BAND_PX = 3;
/** A press this close to the scrollbar's handle takes the handle. */
const THUMB_RADIUS_PX = 7;

export function tickPercent(slice: number, depth: number): number {
    return (slice / (depth - 1)) * 100;
}

/** The slice of the nearest tick a press at `y` hits, or null. The handle wins over ticks under it. */
export function tickAt(
    y: number,
    height: number,
    slices: readonly number[],
    depth: number,
    current: number,
): number | null {
    const at = (slice: number) => (tickPercent(slice, depth) / 100) * height;
    if (Math.abs(y - at(current)) <= THUMB_RADIUS_PX) return null;
    let hit: number | null = null;
    let best: number = TICK_BAND_PX;
    for (const slice of slices) {
        const distance = Math.abs(y - at(slice));
        if (distance <= best) {
            best = distance;
            hit = slice;
        }
    }
    return hit;
}
