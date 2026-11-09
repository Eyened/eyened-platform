import type { Matrix } from "$lib/matrix";
import { AffineRegistration } from "$lib/registration/affine";
import {
    getPointsetRegistrations,
    type PointsetLandmark,
} from "$lib/registration/pointsetRegistration";
import type { RegistrationItem } from "$lib/registration/registrationItem";

/** Direct affine edge only. Multi-hop and non-affine edges are ignored. */
export function directAffineMatrix(
    item: RegistrationItem | undefined,
): Matrix | null {
    if (item instanceof AffineRegistration) return item.M;
    return null;
}

/** Affine from one annotation's landmarks. Ignores other graph edges. */
export function affineFromFormData(
    formData: unknown,
    fromId: string,
    toId: string,
): Matrix | null {
    if (!formData || typeof formData !== "object" || Array.isArray(formData)) {
        return null;
    }
    const items = getPointsetRegistrations(
        formData as { [img_id: string]: PointsetLandmark[] },
    );
    for (const item of items) {
        if (item.source === fromId && item.target === toId) return item.M;
        if (item.source === toId && item.target === fromId) {
            return item.inverse.M;
        }
    }
    return null;
}
