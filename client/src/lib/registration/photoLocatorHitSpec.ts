import {
    CirclePhotoLocator,
    LinePhotoLocator,
    type PhotoLocator,
} from "./photoLocators";

export type HitSpecResult = {
    x: number;
    y: number;
    index: number;
    d: number;
    delta: number;
};

export type PhotoLocatorHitSpec = {
    readonly kind: "raster" | "radial" | "circular" | "mixed";
    query(p: { x: number; y: number }): HitSpecResult | undefined;
};

type RasterMember = {
    loc: LinePhotoLocator;
    offset: number; // signed along mean normal
    delta: number;
};

function meanNormal(lines: LinePhotoLocator[]): { nx: number; ny: number } {
    let nx = 0;
    let ny = 0;
    for (const l of lines) {
        const dx = l.end.x - l.start.x;
        const dy = l.end.y - l.start.y;
        const len = Math.hypot(dx, dy) || 1;
        nx += -dy / len;
        ny += dx / len;
    }
    const nlen = Math.hypot(nx, ny) || 1;
    return { nx: nx / nlen, ny: ny / nlen };
}

function buildRasterFamily(lines: LinePhotoLocator[]): PhotoLocatorHitSpec {
    const { nx, ny } = meanNormal(lines);
    const members: RasterMember[] = lines.map((loc) => {
        const mx = (loc.start.x + loc.end.x) / 2;
        const my = (loc.start.y + loc.end.y) / 2;
        return { loc, offset: mx * nx + my * ny, delta: 1 };
    });
    members.sort((a, b) => a.offset - b.offset);
    for (let i = 0; i < members.length; i++) {
        const gaps: number[] = [];
        if (i > 0) gaps.push(members[i].offset - members[i - 1].offset);
        if (i < members.length - 1)
            gaps.push(members[i + 1].offset - members[i].offset);
        members[i].delta = gaps.length ? Math.min(...gaps) / 2 : 1;
    }

    return {
        kind: "raster",
        query(p) {
            let best: HitSpecResult | undefined;
            let bestScore = Infinity;
            for (const m of members) {
                const { loc, delta } = m;
                const lx = loc.end.x - loc.start.x;
                const ly = loc.end.y - loc.start.y;
                const len = Math.hypot(lx, ly);
                if (len < 1e-6) continue;
                const ptx = p.x - loc.start.x;
                const pty = p.y - loc.start.y;
                const parallel = (ptx * lx + pty * ly) / len;
                if (parallel < 0 || parallel > len) continue;
                const d = Math.abs(lx * pty - ly * ptx) / len;
                if (d > delta) continue;
                const score = d / delta;
                if (
                    score < bestScore ||
                    (score === bestScore && d < (best?.d ?? Infinity))
                ) {
                    bestScore = score;
                    best = {
                        x: (loc.width * parallel) / len,
                        y: loc.index + 0.5,
                        index: loc.index,
                        d,
                        delta,
                    };
                }
            }
            return best;
        },
    };
}

/** Task 1: lines → raster only. Tasks 2–3 extend classification. */
export function buildPhotoLocatorHitSpec(
    locators: PhotoLocator[],
): PhotoLocatorHitSpec {
    const lines = locators.filter(
        (l): l is LinePhotoLocator => l instanceof LinePhotoLocator,
    );
    const circles = locators.filter(
        (l): l is CirclePhotoLocator => l instanceof CirclePhotoLocator,
    );
    if (circles.length) {
        throw new Error("circular families: implement in Task 3");
    }
    if (!lines.length) {
        return { kind: "raster", query: () => undefined };
    }
    // Task 2 replaces this with classifyLines(lines)
    return buildRasterFamily(lines);
}
