import { Matrix, getMatrixFromPointSets } from "$lib/matrix";
import type { Position2D } from "$lib/types";
import { AffineRegistration } from "./affine";

/** Landmark as stored in Pointset registration form_data (may carry OCT index). */
export type PointsetLandmark =
    | (Position2D & { index?: number | null })
    | null
    | undefined;

/**
 * Form_data keys are ImageInstance PublicIDs, but enface viewers / OCT↔proj
 * edges use `${id}_proj`. Affine must live on those enface nodes so the path
 * does not go through ProjToOCT (which moves y→index and leaves y=0).
 *
 * Coordinate convention (matches OCTToProj / ProjToOCT), classified **per point**:
 * - Plain 2D (no `index`): (x, y) image pixels → node = PublicID
 * - Enface `*_proj` (`index: null`): stored (x, y) is already (x, index-space) → node = `${id}_proj`
 * - OCT volume (`index: number`): enface coords are (x, index + 0.5) → node = `${id}_proj`
 *
 * Volume and `*_proj` may share one PublicID key; those points are mapped
 * individually onto `*_proj`. Plain-2D pixels mixed into that list are dropped
 * (nulled) so we never treat a B-scan row as enface y.
 */
type LandmarkKind = "plain" | "proj" | "volume";

function landmarkKind(p: Position2D & { index?: number | null }): LandmarkKind {
    if (typeof p.index === "number") return "volume";
    if ("index" in p && p.index === null) return "proj";
    return "plain";
}

function toEnfacePoint(
    p: Position2D & { index?: number | null },
): Position2D | null {
    const kind = landmarkKind(p);
    if (kind === "volume") return { x: p.x, y: p.index! + 0.5 };
    if (kind === "proj") return { x: p.x, y: p.y };
    return null;
}

export function toEnfaceRegistrationPoints(
    publicId: string,
    points: PointsetLandmark[],
): { nodeId: string; points: (Position2D | null | undefined)[] } {
    const kinds = new Set<LandmarkKind>();
    for (const p of points) {
        if (p != null) kinds.add(landmarkKind(p));
    }
    if (kinds.size === 0) {
        return { nodeId: publicId, points };
    }

    const needsProj = kinds.has("volume") || kinds.has("proj");
    if (!needsProj) {
        return { nodeId: publicId, points };
    }

    return {
        nodeId: `${publicId}_proj`,
        points: points.map((p) => (p == null ? p : toEnfacePoint(p))),
    };
}

export function getPointsetRegistrations(data: {
    [img_id: string]: PointsetLandmark[];
}): AffineRegistration[] {
    const result: AffineRegistration[] = [];
    const keys = Object.keys(data).sort();

    const enface = new Map<
        string,
        { nodeId: string; points: (Position2D | null | undefined)[] }
    >();
    for (const key of keys) {
        enface.set(key, toEnfaceRegistrationPoints(key, data[key] ?? []));
    }

    for (let i = 0; i < keys.length; i++) {
        const sourceKey = keys[i]!;
        const source = enface.get(sourceKey)!;

        for (let j = i + 1; j < keys.length; j++) {
            const targetKey = keys[j]!;
            const target = enface.get(targetKey)!;

            const M = getMatrixFromPointSets(source.points, target.points);
            if (M) {
                result.push(
                    new AffineRegistration(source.nodeId, target.nodeId, M),
                );
            }
        }
    }
    return result;
}

export interface AffineItem {
    image0: number;
    image1: number;
    transform: [number, number, number, number, number, number];
}
function getAffineItem(data: AffineItem) {
    const source = `${data.image0}`;
    const target = `${data.image1}`;
    const [a, b, c, d, e, f] = data.transform;
    // the order of elements in the matrix is different
    const M = new Matrix(a, c, e, b, d, f);
    return new AffineRegistration(source, target, M);
}

export function getAffineTransforms(data: AffineItem[]): AffineRegistration[] {
    return data.map(getAffineItem);
}
