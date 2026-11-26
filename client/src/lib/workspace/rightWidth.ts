/** The right column's width when open, and its smallest; reset goes back here. */
export const RIGHT_MIN_PX = 288;
/** The right column's largest width. */
export const RIGHT_MAX_PX = 480;
/** The viewport grid keeps at least this much beside the right column. */
export const GRID_MIN_PX = 320;
/** One arrow-key step of the right column's splitter. */
export const RIGHT_STEP_PX = 16;

/** The largest width the room allows; the column gives way before the grid drops below its minimum. */
export function rightMax(room: number): number {
    return Math.max(RIGHT_MIN_PX, Math.min(RIGHT_MAX_PX, room - GRID_MIN_PX));
}

/** The width a user set, within what the room shared by grid and column allows. */
export function rightWidth(saved: number, room: number): number {
    return Math.min(Math.max(saved, RIGHT_MIN_PX), rightMax(room));
}
