import { bakeHopGlsl } from "./enfaceToProj";
import { composeGlslPath } from "./composeGlslPath";
import type { Registration } from "./registration.svelte";

export function glslPathBetween(
    registration: Registration,
    fromId: string,
    toId: string,
    sizeOf: (id: string) => [number, number] | undefined,
): string | null {
    const path = registration.getPath(fromId, toId);
    if (!path || path.length < 2) return null;
    const hops: string[] = [];
    for (let i = 0; i < path.length - 1; i++) {
        const source = path[i]!;
        const target = path[i + 1]!;
        const item = registration.getRegistrationItem(source, target);
        const srcSize = sizeOf(source);
        const dstSize = sizeOf(target);
        if (!item || !srcSize || !dstSize) return null;
        const hop = bakeHopGlsl(item, srcSize, dstSize);
        if (!hop) return null;
        hops.push(hop);
    }
    return composeGlslPath(hops);
}
