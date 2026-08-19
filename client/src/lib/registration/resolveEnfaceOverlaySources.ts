import type { EnfaceProjectionMode } from "$lib/viewer/viewer-utils";
import type { EnfaceProjectionManager } from "$lib/viewer-window/enfaceProjectionManager.svelte";
import { bakeHopGlsl } from "./enfaceToProj";
import { composeGlslPath } from "./composeGlslPath";
import type { Registration } from "./registration.svelte";

export type EnfaceOverlaySourceResolved = {
    octPublicId: string;
    manager: EnfaceProjectionManager;
    mappingGlsl: string;
    mode: EnfaceProjectionMode;
    sizePrimary: [number, number];
    sizeSecondary: [number, number];
    /** True for the real `_proj` viewer (identity UV); linked hops stay false. */
    identityMapping: boolean;
};

export function resolveEnfaceOverlaySources(args: {
    imageId: string;
    imageWidth: number;
    imageHeight: number;
    registration: Registration;
    managers: ReadonlyMap<string, EnfaceProjectionManager>;
    /** Pixel size lookup for intermediate path nodes (and current image). */
    getImageSize: (imageId: string) => [number, number] | undefined;
    /** Mode for the real _proj viewer (single source). */
    projMode: EnfaceProjectionMode;
    /** Per-OCT modes for linked viewers; missing key ⇒ "off". */
    linkedModes: ReadonlyMap<string, EnfaceProjectionMode>;
}): EnfaceOverlaySourceResolved[] {
    // Track Registration.revision here (not via an unused caller-passed arg) so
    // $derived.by callers re-resolve when items import after the viewer mounts.
    void args.registration.revision;

    const sizePrimary: [number, number] = [args.imageWidth, args.imageHeight];

    if (args.imageId.endsWith("_proj")) {
        const octPublicId = args.imageId.slice(0, -"_proj".length);
        const manager = args.managers.get(octPublicId);
        if (!manager) {
            return [];
        }
        return [
            {
                octPublicId,
                manager,
                mappingGlsl: composeGlslPath([]),
                mode: args.projMode,
                sizePrimary,
                sizeSecondary: sizePrimary,
                identityMapping: true,
            },
        ];
    }

    const sources: EnfaceOverlaySourceResolved[] = [];
    for (const [octPublicId, manager] of args.managers) {
        const projId = `${octPublicId}_proj`;
        const path = args.registration.getPath(args.imageId, projId);
        if (!path || path.length < 2) {
            continue;
        }

        const projSize: [number, number] = [
            manager.octImage.width,
            manager.octImage.depth,
        ];
        const hops: string[] = [];
        let ok = true;
        for (let i = 0; i < path.length - 1; i++) {
            const from = path[i];
            const to = path[i + 1];
            const item = args.registration.getRegistrationItem(from, to);
            if (!item) {
                ok = false;
                break;
            }
            const srcSize =
                from === args.imageId ? sizePrimary : args.getImageSize(from);
            const dstSize = to === projId ? projSize : args.getImageSize(to);
            if (!srcSize || !dstSize) {
                ok = false;
                break;
            }
            const hop = bakeHopGlsl(item, srcSize, dstSize);
            if (!hop) {
                ok = false;
                break;
            }
            hops.push(hop);
        }
        if (!ok) {
            continue;
        }

        sources.push({
            octPublicId,
            manager,
            mappingGlsl: composeGlslPath(hops),
            mode: args.linkedModes.get(octPublicId) ?? "off",
            sizePrimary,
            sizeSecondary: projSize,
            identityMapping: false,
        });
    }
    return sources;
}
