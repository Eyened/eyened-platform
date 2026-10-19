import type { Position } from "$lib/types";
import type { ImageGET } from "../../types/openapi_types";
import { f, mat3 } from "./affine";
import { AffineRegistration } from "./affine";
import { CompositeRegistration } from "./composite";
import { ParabolicRegistration } from "./parabolic";
import {
    CirclePhotoLocator,
    LinePhotoLocator,
    type PhotoLocator,
} from "./photoLocators";
import {
    medianCircularRadiusSpacingPx,
    medianRasterLineSpacingPx,
    rasterStackAxis,
} from "./photoLocatorHitSpec";
import type { RegistrationItem } from "./registrationItem";
import { Matrix } from "$lib/matrix";
import { instances } from "$lib/data/stores.svelte";

/**
 * Bake a single UV→UV hop with concrete pixel sizes.
 * Multi-hop composition cannot share one u_size_primary/secondary pair.
 */
export function bakeHopGlsl(
    item: RegistrationItem,
    srcSize: [number, number],
    dstSize: [number, number],
): string | null {
    if (item instanceof AffineRegistration) {
        return bakeAffineHop(item.M, srcSize, dstSize);
    }
    if (item instanceof ParabolicRegistration) {
        return bakeParabolicHop(item.dx, item.dy, srcSize, dstSize);
    }
    if (item instanceof CompositeRegistration) {
        return bakePixelPath([item], srcSize, dstSize);
    }
    if (item instanceof EnfaceToProjPhotolocations) {
        return bakeEnfaceToProjHop(
            item.photoLocators,
            srcSize,
            dstSize,
            item.maxMatchDistPx,
        );
    }
    return null;
}

export function bakeAffineHop(
    M: Matrix,
    srcSize: [number, number],
    dstSize: [number, number],
): string {
    return `vec2 map_hop(vec2 uv) {
            mat3 transform = ${mat3(M)}
            vec3 transformedUV = transform * vec3(uv * vec2(${f(srcSize[0])}, ${f(srcSize[1])}), 1.0);
            vec2 result = transformedUV.xy / transformedUV.z;
            return result / vec2(${f(dstSize[0])}, ${f(dstSize[1])});
        }`;
}

const PARABOLIC_TERMS = ["1.0", "1.0", "x", "y", "x * x", "x * y", "y * y"];

/**
 * Pixel-space displacement matching ParabolicRegistration.mapping.
 * Each side is dotted on its own against `[1, 1, x, y, x², xy, y²]`,
 * up to the coefficients that side has. An empty side contributes 0.
 */
function parabolicExpr(coeffs: number[]): string {
    const n = Math.min(coeffs.length, PARABOLIC_TERMS.length);
    if (n === 0) return "0.0";
    return PARABOLIC_TERMS.slice(0, n)
        .map((term, i) => `${f(coeffs[i]!)} * ${term}`)
        .join(" + ");
}

function bakeParabolicPixelStep(dx: number[], dy: number[]): string | null {
    if (dx.length === 0 && dy.length === 0) return null;
    return `{
                float x = p.x;
                float y = p.y;
                float dx_val = ${parabolicExpr(dx)};
                float dy_val = ${parabolicExpr(dy)};
                p = vec2(x - dx_val, y - dy_val);
            }`;
}

/**
 * Pixel-space steps for one graph edge. Output pixels of one step are the
 * input pixels of the next, so a chain does not need the sizes of images
 * in between.
 */
export function bakePixelSteps(item: RegistrationItem): string[] | null {
    if (item instanceof AffineRegistration) {
        return [bakeAffinePixelStep(item.M)];
    }
    if (item instanceof ParabolicRegistration) {
        const step = bakeParabolicPixelStep(item.dx, item.dy);
        return step ? [step] : null;
    }
    if (item instanceof CompositeRegistration) {
        if (item.transforms.length === 0) return null;
        const affines = item.transforms.filter(
            (t): t is AffineRegistration => t instanceof AffineRegistration,
        );
        if (affines.length === item.transforms.length) {
            let combined = affines[0]!.M;
            for (let i = 1; i < affines.length; i++) {
                combined = affines[i]!.M.multiply(combined);
            }
            return [bakeAffinePixelStep(combined)];
        }
        const steps: string[] = [];
        for (const transform of item.transforms) {
            const inner = bakePixelSteps(transform);
            if (!inner) return null;
            steps.push(...inner);
        }
        return steps;
    }
    return null;
}

function wrapPixelSteps(
    steps: string[],
    srcSize: [number, number],
    dstSize: [number, number],
): string {
    return `vec2 map_hop(vec2 uv) {
            vec2 p = uv * vec2(${f(srcSize[0])}, ${f(srcSize[1])});
            ${steps.join("\n")}
            return p / vec2(${f(dstSize[0])}, ${f(dstSize[1])});
        }`;
}

/** One UV mapping for a whole path. Only the first and last image sizes are used. */
export function bakePixelPath(
    items: readonly RegistrationItem[],
    srcSize: [number, number],
    dstSize: [number, number],
): string | null {
    const steps: string[] = [];
    for (const item of items) {
        const part = bakePixelSteps(item);
        if (!part) return null;
        steps.push(...part);
    }
    if (steps.length === 0) return null;
    return wrapPixelSteps(steps, srcSize, dstSize);
}

export function bakeParabolicHop(
    dx: number[],
    dy: number[],
    srcSize: [number, number],
    dstSize: [number, number],
): string | null {
    const step = bakeParabolicPixelStep(dx, dy);
    if (!step) return null;
    return wrapPixelSteps([step], srcSize, dstSize);
}

function bakeAffinePixelStep(M: Matrix): string {
    return `{
                mat3 transform = ${mat3(M)}
                vec3 tp = transform * vec3(p, 1.0);
                p = tp.xy / tp.z;
            }`;
}

/** Direct enface → `{oct}_proj` edge derived from photo locators (for GPU sampling). */
export class EnfaceToProjPhotolocations implements RegistrationItem {
    /** Sizes are baked at resolve time via bakeHopGlsl — leave empty here. */
    glslMapping = "";

    constructor(
        public readonly source: string,
        public readonly target: string,
        public readonly photoLocators: PhotoLocator[],
        public readonly projWidth: number,
        public readonly projDepth: number,
        /** Raster-only: max perpendicular match distance in enface px (null = ungated). */
        public readonly maxMatchDistPx: number | null = null,
    ) {}

    mapping(p: Position): Position | undefined {
        let minDistance = Infinity;
        let best: Position | undefined;
        for (const locator of this.photoLocators) {
            const { distance, position } = locator.enfaceToOCT(p);
            if (distance < minDistance) {
                minDistance = distance;
                best = {
                    x: position.x,
                    y: position.index + 0.5,
                    index: 0,
                };
            }
        }
        if (
            best &&
            this.maxMatchDistPx != null &&
            minDistance > this.maxMatchDistPx
        ) {
            return undefined;
        }
        return best;
    }

    get inverse(): RegistrationItem {
        return new ProjToEnfacePhotolocations(
            this.target,
            this.source,
            this.photoLocators,
            this.projWidth,
            this.projDepth,
        );
    }
}

/** Inverse of EnfaceToProj — CPU only for graph completeness; no GLSL yet. */
export class ProjToEnfacePhotolocations implements RegistrationItem {
    glslMapping = "";

    constructor(
        public readonly source: string,
        public readonly target: string,
        public readonly photoLocators: PhotoLocator[],
        public readonly projWidth: number,
        public readonly projDepth: number,
    ) {}

    mapping(p: Position): Position | undefined {
        const index = Math.round(
            Math.max(0, Math.min(p.y, this.projDepth - 1)),
        );
        const locator = this.photoLocators.find((loc) => loc.index === index);
        if (!locator) {
            return undefined;
        }
        return locator.OCTToEnface({ x: p.x, y: 0, index });
    }

    get inverse(): RegistrationItem {
        return new EnfaceToProjPhotolocations(
            this.target,
            this.source,
            this.photoLocators,
            this.projWidth,
            this.projDepth,
            // Inverse does not use maxMatchDistPx; forward edge owns the gate.
        );
    }
}

/**
 * Prefer DICOM SliceThickness (mm) converted via enface mm/px; otherwise median
 * spacing. Returns a *half*-gap / half-thickness so the outer catchment matches
 * ±T/2 (I4), not a full inter-slice overshoot.
 */
export function resolveRasterMaxMatchDistPx(
    lines: LinePhotoLocator[],
    sliceThicknessMm?: number | null,
    enfaceMmPerPx?: number | null,
): number | null {
    if (
        sliceThicknessMm != null &&
        sliceThicknessMm > 0 &&
        enfaceMmPerPx != null &&
        enfaceMmPerPx > 0
    ) {
        return sliceThicknessMm / enfaceMmPerPx / 2;
    }
    const median = medianRasterLineSpacingPx(lines);
    if (median != null && median > 0) {
        return median / 2;
    }
    // Singleton line: no neighbor gap — keep a thin strip (hit-spec uses 1px).
    if (lines.length === 1) {
        return 1;
    }
    return null;
}

/** Half radius-gap, or thin annulus for a single circle (C1 Heidelberg case). */
export function resolveCircularMaxMatchDistPx(
    circles: CirclePhotoLocator[],
    sliceThicknessMm?: number | null,
    enfaceMmPerPx?: number | null,
): number | null {
    if (
        sliceThicknessMm != null &&
        sliceThicknessMm > 0 &&
        enfaceMmPerPx != null &&
        enfaceMmPerPx > 0
    ) {
        return sliceThicknessMm / enfaceMmPerPx / 2;
    }
    const median = medianCircularRadiusSpacingPx(circles);
    if (median != null && median > 0) {
        return median / 2;
    }
    if (circles.length === 1 && circles[0].radius > 0) {
        return Math.max(circles[0].radius * 0.05, 1);
    }
    return null;
}

function enfaceMmPerPxAlongStack(
    lines: LinePhotoLocator[],
    enface: ImageGET | undefined,
): number | null {
    if (!enface || lines.length < 1) {
        return null;
    }
    const axis = rasterStackAxis(lines);
    const r =
        axis === "vertical"
            ? enface.resolution_vertical
            : enface.resolution_horizontal;
    return r != null && r > 0 ? r : null;
}

function enfaceMmPerPxIsotropic(enface: ImageGET | undefined): number | null {
    if (!enface) {
        return null;
    }
    const h = enface.resolution_horizontal;
    const v = enface.resolution_vertical;
    if (h != null && h > 0 && v != null && v > 0) {
        return (h + v) / 2;
    }
    if (h != null && h > 0) {
        return h;
    }
    if (v != null && v > 0) {
        return v;
    }
    return null;
}

export function bakeEnfaceToProjHop(
    photoLocators: PhotoLocator[],
    srcSize: [number, number],
    dstSize: [number, number],
    maxMatchDistPx: number | null = null,
): string | null {
    if (!photoLocators.length) {
        return null;
    }

    const blocks: string[] = [];
    for (const loc of photoLocators) {
        if (loc instanceof LinePhotoLocator) {
            blocks.push(`{
                vec2 start = vec2(${f(loc.start.x)}, ${f(loc.start.y)});
                vec2 end = vec2(${f(loc.end.x)}, ${f(loc.end.y)});
                vec2 lineVec = end - start;
                float len = length(lineVec);
                if (len > 1e-6) {
                    vec2 ptVec = p - start;
                    float parallel = dot(ptVec, lineVec) / len;
                    float dist = abs(lineVec.x * ptVec.y - lineVec.y * ptVec.x) / len;
                    float ox = ${f(loc.width)} * parallel / len;
                    float oy = ${f(loc.index)} + 0.5;
                    if (dist < bestDist) {
                        bestDist = dist;
                        best = vec2(ox, oy);
                    }
                }
            }`);
        } else if (loc instanceof CirclePhotoLocator) {
            blocks.push(`{
                const float TWO_PI = 6.283185307179586;
                vec2 center = vec2(${f(loc.center.x)}, ${f(loc.center.y)});
                vec2 vecc = p - center;
                float radius = ${f(loc.radius)};
                float dist = abs(length(vecc) - radius);
                float angle = atan(vecc.y, vecc.x) - ${f(loc.start_angle)};
                float t = fract(angle / TWO_PI);
                float ox = ${f(loc.width)} * t;
                float oy = ${f(loc.index)} + 0.5;
                if (dist < bestDist) {
                    bestDist = dist;
                    best = vec2(ox, oy);
                }
            }`);
        }
    }

    if (!blocks.length) {
        return null;
    }

    const gate =
        maxMatchDistPx != null && maxMatchDistPx > 0
            ? `if (bestDist > ${f(maxMatchDistPx)}) {
                return vec2(-1.0);
            }
            `
            : "";

    return `vec2 map_hop(vec2 uv) {
            vec2 p = uv * vec2(${f(srcSize[0])}, ${f(srcSize[1])});
            float bestDist = 1e20;
            vec2 best = vec2(0.0);
            ${blocks.join("\n")}
            ${gate}return best / vec2(${f(dstSize[0])}, ${f(dstSize[1])});
        }`;
}

/** Build enface ↔ `_proj` edges for an OCT volume that has photo locators. */
export function enfaceToProjRegistrationItems(
    photoLocators: PhotoLocator[],
    octPublicId: string,
    projWidth: number,
    projDepth: number,
    sliceThicknessMm?: number | null,
): RegistrationItem[] {
    const projId = `${octPublicId}_proj`;
    const byEnface = new Map<string, PhotoLocator[]>();
    for (const loc of photoLocators) {
        const list = byEnface.get(loc.enfaceImageId) ?? [];
        list.push(loc);
        byEnface.set(loc.enfaceImageId, list);
    }

    const items: RegistrationItem[] = [];
    for (const [enfaceId, locs] of byEnface) {
        const lines = locs.filter(
            (l): l is LinePhotoLocator => l instanceof LinePhotoLocator,
        );
        const circles = locs.filter(
            (l): l is CirclePhotoLocator => l instanceof CirclePhotoLocator,
        );
        let maxMatchDistPx: number | null = null;
        const enface = instances.get(enfaceId);
        if (circles.length === 0 && lines.length >= 1) {
            maxMatchDistPx = resolveRasterMaxMatchDistPx(
                lines,
                sliceThicknessMm,
                enfaceMmPerPxAlongStack(lines, enface),
            );
        } else if (lines.length === 0 && circles.length >= 1) {
            maxMatchDistPx = resolveCircularMaxMatchDistPx(
                circles,
                sliceThicknessMm,
                enfaceMmPerPxIsotropic(enface),
            );
        }
        items.push(
            new EnfaceToProjPhotolocations(
                enfaceId,
                projId,
                locs,
                projWidth,
                projDepth,
                maxMatchDistPx,
            ),
        );
    }
    return items;
}
