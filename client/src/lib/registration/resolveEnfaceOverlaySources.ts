import type { EnfaceProjectionMode } from "$lib/viewer/viewer-utils";
import type { EnfaceProjectionManager } from "$lib/viewer-window/enfaceProjectionManager.svelte";
import { AffineRegistration } from "./affine";
import { composeGlslPath } from "./composeGlslPath";
import type { Registration } from "./registration";

export type EnfaceOverlaySourceResolved = {
    octPublicId: string;
    manager: EnfaceProjectionManager;
    mappingGlsl: string;
    mode: EnfaceProjectionMode;
    sizePrimary: [number, number];
    sizeSecondary: [number, number];
};

export function resolveEnfaceOverlaySources(args: {
    imageId: string;
    imageWidth: number;
    imageHeight: number;
    registration: Registration;
    managers: ReadonlyMap<string, EnfaceProjectionManager>;
    /** Mode for the real _proj viewer (single source). */
    projMode: EnfaceProjectionMode;
    /** Per-OCT modes for linked viewers; missing key ⇒ "off". */
    linkedModes: ReadonlyMap<string, EnfaceProjectionMode>;
}): EnfaceOverlaySourceResolved[] {
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
            },
        ];
    }

    const sources: EnfaceOverlaySourceResolved[] = [];
    for (const target of args.registration.listDirectTargets(args.imageId)) {
        if (!target.endsWith("_proj")) {
            continue;
        }
        const item = args.registration.getRegistrationItem(
            args.imageId,
            target,
        );
        if (!(item instanceof AffineRegistration) || !item.glslMapping.trim()) {
            continue;
        }
        const octPublicId = target.slice(0, -"_proj".length);
        const manager = args.managers.get(octPublicId);
        if (!manager) {
            continue;
        }
        sources.push({
            octPublicId,
            manager,
            mappingGlsl: composeGlslPath([item.glslMapping]),
            mode: args.linkedModes.get(octPublicId) ?? "off",
            sizePrimary,
            sizeSecondary: [manager.octImage.width, manager.octImage.depth],
        });
    }
    return sources;
}
