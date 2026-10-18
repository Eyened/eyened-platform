import type { Matrix } from "$lib/matrix";
import { AffineRegistration } from "$lib/registration/affine";
import type { RegistrationItem } from "$lib/registration/registrationItem";

/** Direct affine edge only. Multi-hop and non-affine edges are ignored. */
export function directAffineMatrix(
    item: RegistrationItem | undefined,
): Matrix | null {
    if (item instanceof AffineRegistration) return item.M;
    return null;
}

/** First checked image in top-row order, other than the fixed image. */
export function firstBlendOverlay(
    orderedImageIds: readonly string[],
    fixedImageId: string,
    overlayImageIds: readonly string[],
): string | undefined {
    const selected = new Set(overlayImageIds);
    return orderedImageIds.find(
        (id) => id !== fixedImageId && selected.has(id),
    );
}
