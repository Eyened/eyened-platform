import { bakeHopGlsl, bakePixelPath } from "./enfaceToProj";
import { composeGlslPath } from "./composeGlslPath";
import type { Registration } from "./registration.svelte";
import type { RegistrationItem } from "./registrationItem";

/**
 * Baked `vec2 mapping(vec2 uv)` from one image into another.
 * The path can include affine, parabolic, composite, and enface hops.
 * Returns null when no path can be baked.
 */
export function glslPathBetween(
    registration: Registration,
    fromId: string,
    toId: string,
    getImageSize: (imageId: string) => [number, number] | undefined,
): string | null {
    if (fromId === toId) return composeGlslPath([]);
    const path = registration.getPath(fromId, toId);
    if (!path || path.length < 2) return null;

    const items: RegistrationItem[] = [];
    for (let i = 0; i < path.length - 1; i++) {
        const from = path[i]!;
        const to = path[i + 1]!;
        const item = registration.getRegistrationItem(from, to);
        if (!item) return null;
        items.push(item);
    }

    // Affine, parabolic, and composite edges stay in pixel space, so an
    // image that only sits between two hops does not need to be open.
    const srcSize = getImageSize(path[0]!);
    const dstSize = getImageSize(path[path.length - 1]!);
    if (srcSize && dstSize) {
        const pixelHop = bakePixelPath(items, srcSize, dstSize);
        if (pixelHop) return composeGlslPath([pixelHop]);
    }

    const hops: string[] = [];
    for (let i = 0; i < path.length - 1; i++) {
        const from = path[i]!;
        const to = path[i + 1]!;
        const src = getImageSize(from);
        const dst = getImageSize(to);
        if (!src || !dst) return null;
        const hop = bakeHopGlsl(items[i]!, src, dst);
        if (!hop) return null;
        hops.push(hop);
    }
    return composeGlslPath(hops);
}
