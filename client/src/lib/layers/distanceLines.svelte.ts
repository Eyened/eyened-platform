import type { Position2D } from "$lib/types";
import type { Scale } from "./imageScale";

/** One distance line on an image, on the B-scan it was drawn on. */
export class Line {
    start = $state({ x: 0, y: 0 });
    end = $state({ x: 0, y: 0 });

    constructor(
        start: Position2D,
        end: Position2D,
        public readonly index: number,
    ) {
        this.start = start;
        this.end = end;
    }
    *[Symbol.iterator]() {
        yield this.start;
        yield this.end;
    }
}

/** An image's distance lines for the session, and the current one: the last drawn or clicked. */
export class DistanceLines {
    lines: Line[] = $state([]);
    current: Line | undefined = $state();
    /** The line a Distance lines row points at while it is hovered or focused. */
    highlighted: Line | undefined = $state();
    /** The line between its first click and its second; Esc drops it first. */
    drawing: Line | undefined;

    add(line: Line): void {
        this.lines = [...this.lines, line];
        this.current = line;
    }

    remove(line: Line): void {
        this.lines = this.lines.filter((l) => l !== line);
        if (this.current === line) this.current = undefined;
        if (this.highlighted === line) this.highlighted = undefined;
        if (this.drawing === line) this.drawing = undefined;
    }

    clear(): void {
        this.lines = [];
        this.current = undefined;
        this.highlighted = undefined;
        this.drawing = undefined;
    }
}

/** A line's length: µm or mm with a scale, px without. */
export function lengthText(line: Line, scale: Scale | null): string {
    const dx = line.end.x - line.start.x;
    const dy = line.end.y - line.start.y;
    if (!scale) return `${Math.hypot(dx, dy).toFixed(0)} px`;
    const um = Math.hypot(dx * scale.x, dy * scale.y);
    return um > 1000 ? `${(um / 1000).toFixed(2)} mm` : `${um.toFixed(2)} µm`;
}
