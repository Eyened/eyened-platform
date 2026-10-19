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
