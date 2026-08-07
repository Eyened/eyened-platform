import type { Position } from "$lib/types";
import { f, mat3 } from "./affine";
import { AffineRegistration } from "./affine";
import { CompositeRegistration } from "./composite";
import { ParabolicRegistration } from "./parabolic";
import {
    CirclePhotoLocator,
    LinePhotoLocator,
    type PhotoLocator,
} from "./photoLocators";
import type { RegistrationItem } from "./registrationItem";
import { Matrix } from "$lib/matrix";

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
        return bakeCompositeHop(item, srcSize, dstSize);
    }
    if (item instanceof EnfaceToProjPhotolocations) {
        return bakeEnfaceToProjHop(item.photoLocators, srcSize, dstSize);
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

/** Pixel-space displacement matching ParabolicRegistration.mapping. */
function bakeParabolicPixelStep(dx: number[], dy: number[]): string | null {
    if (dx.length !== 7 || dy.length !== 7) {
        return null;
    }
    return `{
                float x = p.x;
                float y = p.y;
                float dx_val = ${f(dx[0])} + ${f(dx[1])} + ${f(dx[2])} * x + ${f(dx[3])} * y + ${f(dx[4])} * x * x + ${f(dx[5])} * x * y + ${f(dx[6])} * y * y;
                float dy_val = ${f(dy[0])} + ${f(dy[1])} + ${f(dy[2])} * x + ${f(dy[3])} * y + ${f(dy[4])} * x * x + ${f(dy[5])} * x * y + ${f(dy[6])} * y * y;
                p = vec2(x - dx_val, y - dy_val);
            }`;
}

export function bakeParabolicHop(
    dx: number[],
    dy: number[],
    srcSize: [number, number],
    dstSize: [number, number],
): string | null {
    const step = bakeParabolicPixelStep(dx, dy);
    if (!step) {
        return null;
    }
    return `vec2 map_hop(vec2 uv) {
            vec2 p = uv * vec2(${f(srcSize[0])}, ${f(srcSize[1])});
            ${step}
            return p / vec2(${f(dstSize[0])}, ${f(dstSize[1])});
        }`;
}

function bakeAffinePixelStep(M: Matrix): string {
    return `{
                mat3 transform = ${mat3(M)}
                vec3 tp = transform * vec3(p, 1.0);
                p = tp.xy / tp.z;
            }`;
}

function bakeCompositeHop(
    item: CompositeRegistration,
    srcSize: [number, number],
    dstSize: [number, number],
): string | null {
    if (item.transforms.length === 0) {
        return null;
    }

    const affines = item.transforms.filter(
        (t): t is AffineRegistration => t instanceof AffineRegistration,
    );
    if (affines.length === item.transforms.length) {
        // CPU applies T0 then T1 … → combined = Tn * … * T0
        let combined = affines[0].M;
        for (let i = 1; i < affines.length; i++) {
            combined = affines[i].M.multiply(combined);
        }
        return bakeAffineHop(combined, srcSize, dstSize);
    }

    // Mixed affine/parabolic: same continuous pixel space as CompositeRegistration.mapping.
    const steps: string[] = [];
    for (const t of item.transforms) {
        if (t instanceof AffineRegistration) {
            steps.push(bakeAffinePixelStep(t.M));
        } else if (t instanceof ParabolicRegistration) {
            const step = bakeParabolicPixelStep(t.dx, t.dy);
            if (!step) {
                return null;
            }
            steps.push(step);
        } else {
            return null;
        }
    }
    return `vec2 map_hop(vec2 uv) {
            vec2 p = uv * vec2(${f(srcSize[0])}, ${f(srcSize[1])});
            ${steps.join("\n")}
            return p / vec2(${f(dstSize[0])}, ${f(dstSize[1])});
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
        );
    }
}

export function bakeEnfaceToProjHop(
    photoLocators: PhotoLocator[],
    srcSize: [number, number],
    dstSize: [number, number],
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
                vec2 center = vec2(${f(loc.center.x)}, ${f(loc.center.y)});
                vec2 vecc = p - center;
                float radius = ${f(loc.radius)};
                float dist = abs(length(vecc) - radius);
                float angle = atan(vecc.y, vecc.x) - ${f(loc.start_angle)};
                float r = angle / (2.0 * 3.141592653589793);
                float ox = ${f(loc.width)} * r;
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

    return `vec2 map_hop(vec2 uv) {
            vec2 p = uv * vec2(${f(srcSize[0])}, ${f(srcSize[1])});
            float bestDist = 1e20;
            vec2 best = vec2(0.0);
            ${blocks.join("\n")}
            return best / vec2(${f(dstSize[0])}, ${f(dstSize[1])});
        }`;
}

/** Build enface ↔ `_proj` edges for an OCT volume that has photo locators. */
export function enfaceToProjRegistrationItems(
    photoLocators: PhotoLocator[],
    octPublicId: string,
    projWidth: number,
    projDepth: number,
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
        items.push(
            new EnfaceToProjPhotolocations(
                enfaceId,
                projId,
                locs,
                projWidth,
                projDepth,
            ),
        );
    }
    return items;
}
