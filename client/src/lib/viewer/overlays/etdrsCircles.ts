const [C, I, O] = [1, 3, 6];

/** ETDRS circle sizes, smallest first: diameters in mm, as fractions of the 1, 3 and 6 mm rings. */
export const ETDRS_CIRCLES = {
    C0: C / 16,
    C1: C / 8,
    C2: C / 4,
    I1: I / 8,
    I2: I / 4,
    O1: O / 8,
    O2: O / 4,
};
export type CircleSize = keyof typeof ETDRS_CIRCLES;
export const CIRCLE_SIZES = Object.keys(ETDRS_CIRCLES) as CircleSize[];
