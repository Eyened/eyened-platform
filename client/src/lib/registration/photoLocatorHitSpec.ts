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

function lineUnit(l: LinePhotoLocator) {
    const dx = l.end.x - l.start.x;
    const dy = l.end.y - l.start.y;
    const len = Math.hypot(dx, dy) || 1;
    return { ux: dx / len, uy: dy / len, len };
}

/** Least-squares hub: point minimizing sum of squared distances to infinite lines. */
function estimateHub(lines: LinePhotoLocator[]): { x: number; y: number } {
    let a00 = 0,
        a01 = 0,
        a11 = 0,
        b0 = 0,
        b1 = 0;
    for (const l of lines) {
        const { ux, uy } = lineUnit(l);
        const nx = -uy;
        const ny = ux;
        a00 += nx * nx;
        a01 += nx * ny;
        a11 += ny * ny;
        const d = nx * l.start.x + ny * l.start.y;
        b0 += nx * d;
        b1 += ny * d;
    }
    const det = a00 * a11 - a01 * a01;
    if (Math.abs(det) < 1e-8) {
        let x = 0,
            y = 0;
        for (const l of lines) {
            x += l.start.x;
            y += l.start.y;
        }
        return { x: x / lines.length, y: y / lines.length };
    }
    return {
        x: (a11 * b0 - a01 * b1) / det,
        y: (-a01 * b0 + a00 * b1) / det,
    };
}

function distPointToLine(p: { x: number; y: number }, l: LinePhotoLocator) {
    const lx = l.end.x - l.start.x;
    const ly = l.end.y - l.start.y;
    const len = Math.hypot(lx, ly) || 1;
    return Math.abs(lx * (p.y - l.start.y) - ly * (p.x - l.start.x)) / len;
}

function median(vals: number[]): number {
    const s = [...vals].sort((a, b) => a - b);
    const m = Math.floor(s.length / 2);
    return s.length % 2 ? s[m] : 0.5 * (s[m - 1] + s[m]);
}

function wrapPi(a: number) {
    while (a <= -Math.PI) a += 2 * Math.PI;
    while (a > Math.PI) a -= 2 * Math.PI;
    return a;
}

function classifyLines(lines: LinePhotoLocator[]): "raster" | "radial" {
    if (lines.length < 2) return "raster";
    const hub = estimateHub(lines);
    const dists = lines.map((l) => distPointToLine(hub, l));
    const lengths = lines.map((l) => lineUnit(l).len);
    const hubOk = median(dists) < 0.15 * median(lengths);
    const angles = lines.map((l) => {
        const mx = (l.start.x + l.end.x) / 2 - hub.x;
        const my = (l.start.y + l.end.y) / 2 - hub.y;
        return Math.atan2(my, mx);
    });
    let maxSpan = 0;
    for (let i = 0; i < angles.length; i++) {
        for (let j = i + 1; j < angles.length; j++) {
            maxSpan = Math.max(
                maxSpan,
                Math.abs(wrapPi(angles[i] - angles[j])),
            );
        }
    }
    const wideFan = maxSpan > (25 * Math.PI) / 180;
    return hubOk && wideFan ? "radial" : "raster";
}

/**
 * Median consecutive spacing (px) along the mean normal for roughly parallel lines.
 * Null when lines are not parallel enough or fewer than 2.
 */
export function medianRasterLineSpacingPx(
    lines: LinePhotoLocator[],
): number | null {
    if (lines.length < 2) {
        return null;
    }
    const dirs = lines.map(lineUnit);
    const ref = dirs[0];
    const parallelEnough = dirs.every(
        (d) => Math.abs(d.ux * ref.ux + d.uy * ref.uy) > 0.95,
    );
    if (!parallelEnough) {
        return null;
    }
    const members = rasterMembers(lines);
    const gaps: number[] = [];
    for (let i = 1; i < members.length; i++) {
        gaps.push(members[i].offset - members[i - 1].offset);
    }
    return gaps.length ? median(gaps) : null;
}

/** Unit normal of the mean line direction (for choosing enface axis resolution). */
export function rasterStackAxis(
    lines: LinePhotoLocator[],
): "horizontal" | "vertical" {
    const { nx, ny } = meanNormal(lines);
    return Math.abs(ny) >= Math.abs(nx) ? "vertical" : "horizontal";
}

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

function rasterMembers(lines: LinePhotoLocator[]): RasterMember[] {
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
    return members;
}

function buildRasterFamily(lines: LinePhotoLocator[]): PhotoLocatorHitSpec {
    const members = rasterMembers(lines);
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

type RadialMember = {
    loc: LinePhotoLocator;
    angle: number;
    delta: number;
    charR: number;
};

function radialMembers(lines: LinePhotoLocator[]): {
    hub: { x: number; y: number };
    members: RadialMember[];
} {
    const hub = estimateHub(lines);
    const members: RadialMember[] = lines.map((loc) => {
        const mx = (loc.start.x + loc.end.x) / 2 - hub.x;
        const my = (loc.start.y + loc.end.y) / 2 - hub.y;
        return {
            loc,
            angle: Math.atan2(my, mx),
            delta: 1,
            charR: Math.hypot(mx, my) || 1,
        };
    });
    members.sort((a, b) => a.angle - b.angle);
    const charR = median(members.map((m) => m.charR));
    for (let i = 0; i < members.length; i++) {
        const gaps: number[] = [];
        if (i > 0) gaps.push(members[i].angle - members[i - 1].angle);
        if (i < members.length - 1)
            gaps.push(members[i + 1].angle - members[i].angle);
        members[i].delta = gaps.length
            ? Math.min(...gaps) / 2
            : 1 / Math.max(charR, 1);
    }
    return { hub, members };
}

function buildRadialFamily(lines: LinePhotoLocator[]): PhotoLocatorHitSpec {
    const { hub, members } = radialMembers(lines);
    return {
        kind: "radial",
        query(p) {
            const ang = Math.atan2(p.y - hub.y, p.x - hub.x);
            const r = Math.hypot(p.x - hub.x, p.y - hub.y);
            if (r < 1e-6) return undefined;
            let best: HitSpecResult | undefined;
            let bestScore = Infinity;
            for (const m of members) {
                const d = Math.abs(wrapPi(ang - m.angle));
                if (d > m.delta) continue;
                const { loc } = m;
                const lx = loc.end.x - loc.start.x;
                const ly = loc.end.y - loc.start.y;
                const len = Math.hypot(lx, ly) || 1;
                const parallel =
                    ((p.x - loc.start.x) * lx + (p.y - loc.start.y) * ly) / len;
                if (parallel < 0 || parallel > len) continue;
                const score = d / m.delta;
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
                        delta: m.delta,
                    };
                }
            }
            return best;
        },
    };
}

const CENTER_EPS = 2; // px

type CircularMember = { loc: CirclePhotoLocator; delta: number };

function circularMembers(circles: CirclePhotoLocator[]): CircularMember[] {
    const members: CircularMember[] = [...circles]
        .sort((a, b) => a.radius - b.radius)
        .map((loc) => ({ loc, delta: 1 }));
    for (let i = 0; i < members.length; i++) {
        const gaps: number[] = [];
        if (i > 0) gaps.push(members[i].loc.radius - members[i - 1].loc.radius);
        if (i < members.length - 1)
            gaps.push(members[i + 1].loc.radius - members[i].loc.radius);
        members[i].delta = gaps.length ? Math.min(...gaps) / 2 : 1;
    }
    return members;
}

/**
 * Median consecutive radius gap (px) for concentric circles (same center).
 * Null when fewer than 2 circles.
 */
export function medianCircularRadiusSpacingPx(
    circles: CirclePhotoLocator[],
): number | null {
    if (circles.length < 2) {
        return null;
    }
    const members = circularMembers(circles);
    const gaps: number[] = [];
    for (let i = 1; i < members.length; i++) {
        gaps.push(members[i].loc.radius - members[i - 1].loc.radius);
    }
    return gaps.length ? median(gaps) : null;
}

function buildCircularFamily(
    circles: CirclePhotoLocator[],
): PhotoLocatorHitSpec {
    const c = circles[0].center;
    const members = circularMembers(circles);
    return {
        kind: "circular",
        query(p) {
            const dx = p.x - c.x;
            const dy = p.y - c.y;
            const rr = Math.hypot(dx, dy);
            let best: HitSpecResult | undefined;
            let bestScore = Infinity;
            for (const m of members) {
                const d = Math.abs(rr - m.loc.radius);
                if (d > m.delta) continue;
                const angle = Math.atan2(dy, dx) - m.loc.start_angle;
                let t = angle / (2 * Math.PI);
                t = t - Math.floor(t); // fract → [0,1)
                const score = d / m.delta;
                if (
                    score < bestScore ||
                    (score === bestScore && d < (best?.d ?? Infinity))
                ) {
                    bestScore = score;
                    best = {
                        x: m.loc.width * t,
                        y: m.loc.index + 0.5,
                        index: m.loc.index,
                        d,
                        delta: m.delta,
                    };
                }
            }
            return best;
        },
    };
}

function groupCirclesByCenter(
    circles: CirclePhotoLocator[],
): CirclePhotoLocator[][] {
    const groups: CirclePhotoLocator[][] = [];
    for (const cir of circles) {
        let g = groups.find(
            (grp) =>
                Math.hypot(
                    grp[0].center.x - cir.center.x,
                    grp[0].center.y - cir.center.y,
                ) < CENTER_EPS,
        );
        if (!g) {
            g = [];
            groups.push(g);
        }
        g.push(cir);
    }
    return groups;
}

function mergeSpecs(specs: PhotoLocatorHitSpec[]): PhotoLocatorHitSpec {
    if (specs.length === 1) return specs[0];
    return {
        kind: "mixed",
        query(p) {
            let best: HitSpecResult | undefined;
            let bestScore = Infinity;
            for (const s of specs) {
                const hit = s.query(p);
                if (!hit) continue;
                const score = hit.d / hit.delta;
                if (
                    score < bestScore ||
                    (score === bestScore && hit.d < (best?.d ?? Infinity))
                ) {
                    bestScore = score;
                    best = hit;
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
    const specs: PhotoLocatorHitSpec[] = [];
    if (lines.length) {
        specs.push(
            classifyLines(lines) === "radial"
                ? buildRadialFamily(lines)
                : buildRasterFamily(lines),
        );
    }
    for (const g of groupCirclesByCenter(circles)) {
        specs.push(buildCircularFamily(g));
    }
    if (!specs.length) {
        return { kind: "raster", query: () => undefined };
    }
    return mergeSpecs(specs);
}
