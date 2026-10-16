import { blendColours, type Rgb } from "./blendColours";

export type BlendLayer = {
    imageId: string;
    role: "fixed" | "overlay";
    colour: Rgb;
    untinted: boolean;
    draw: boolean;
};

export function blendLayers(input: {
    orderedImageIds: readonly string[];
    fixedImageId: string;
    overlayImageIds: readonly string[];
    hasPath: (overlayId: string, fixedId: string) => boolean;
    canSample: (imageId: string) => boolean;
}): BlendLayer[] {
    const overlays = new Set(input.overlayImageIds);
    const included = input.orderedImageIds.filter(
        (id) => id === input.fixedImageId || overlays.has(id),
    );
    const palette = blendColours(included.length);
    return included.map((imageId, index) => {
        const role = imageId === input.fixedImageId ? "fixed" : "overlay";
        const sampled = input.canSample(imageId);
        const draw =
            role === "fixed"
                ? sampled
                : sampled && input.hasPath(imageId, input.fixedImageId);
        return {
            imageId,
            role,
            colour: palette.colours[index]!,
            untinted: palette.untinted,
            draw,
        };
    });
}

export function selectFixedImage(
    state: { fixedImageId: string; overlayImageIds: readonly string[] },
    nextFixedId: string,
): { fixedImageId: string; overlayImageIds: string[] } {
    const overlayImageIds = state.overlayImageIds.filter((id) => id !== nextFixedId);
    if (state.fixedImageId !== nextFixedId) overlayImageIds.push(state.fixedImageId);
    return { fixedImageId: nextFixedId, overlayImageIds };
}
