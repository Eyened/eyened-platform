import { Matrix } from "$lib/matrix";
import type { SegmentationDataRepresentation } from "../../types/openapi_types";
import {
    convert,
    type SimpleDataRepresentation,
} from "./segmentationConverter";
import type { DrawingArray } from "./mask.svelte";

function isSimpleRepresentation(
    representation: SegmentationDataRepresentation,
): representation is SimpleDataRepresentation {
    return (
        representation === "Binary" ||
        representation === "DualBitMask" ||
        representation === "Probability"
    );
}

function toImageMatrix(rows: number[][] | null | undefined): Matrix {
    if (!rows) return Matrix.identity;
    return Matrix.fromRows(rows);
}

/** Matches cv2.warpPerspective INTER_NEAREST (round half to even). */
function roundHalfToEven(value: number): number {
    const floor = Math.floor(value);
    const fraction = value - floor;
    if (fraction < 0.5) return floor;
    if (fraction > 0.5) return floor + 1;
    return Math.abs(floor % 2) === 0 ? floor : floor + 1;
}

function sampleAt(
    data: DrawingArray,
    width: number,
    height: number,
    x: number,
    y: number,
): number {
    if (x < 0 || y < 0 || x >= width || y >= height) return 0;
    return data[y * width + x];
}

function sampleNearest(
    data: DrawingArray,
    width: number,
    height: number,
    x: number,
    y: number,
): number {
    return sampleAt(
        data,
        width,
        height,
        roundHalfToEven(x),
        roundHalfToEven(y),
    );
}

function sampleBilinear(
    data: DrawingArray,
    width: number,
    height: number,
    x: number,
    y: number,
): number {
    const x0 = Math.floor(x);
    const y0 = Math.floor(y);
    const fx = x - x0;
    const fy = y - y0;
    const v00 = sampleAt(data, width, height, x0, y0);
    const v10 = sampleAt(data, width, height, x0 + 1, y0);
    const v01 = sampleAt(data, width, height, x0, y0 + 1);
    const v11 = sampleAt(data, width, height, x0 + 1, y0 + 1);
    return (
        v00 * (1 - fx) * (1 - fy) +
        v10 * fx * (1 - fy) +
        v01 * (1 - fx) * fy +
        v11 * fx * fy
    );
}

function allocateLike(data: DrawingArray, length: number): DrawingArray {
    const Ctor = data.constructor as new (length: number) => DrawingArray;
    return new Ctor(length);
}

/**
 * Resample `data` onto the destination grid.
 * Each matrix maps that segmentation's pixels into image space.
 * An unset matrix is identity.
 */
function resample(
    data: DrawingArray,
    sourceWidth: number,
    sourceHeight: number,
    destWidth: number,
    destHeight: number,
    sourceMatrix: number[][] | null | undefined,
    destMatrix: number[][] | null | undefined,
    bilinear: boolean,
): DrawingArray {
    const map = toImageMatrix(sourceMatrix).inverse.multiply(
        toImageMatrix(destMatrix),
    );
    const out = allocateLike(data, destWidth * destHeight);
    const round = bilinear && !(data instanceof Float32Array);
    for (let y = 0; y < destHeight; y++) {
        for (let x = 0; x < destWidth; x++) {
            const h = map.g * x + map.h * y + map.i;
            const sx = (map.a * x + map.b * y + map.c) / h;
            const sy = (map.d * x + map.e * y + map.f) / h;
            const value = bilinear
                ? sampleBilinear(data, sourceWidth, sourceHeight, sx, sy)
                : sampleNearest(data, sourceWidth, sourceHeight, sx, sy);
            out[y * destWidth + x] = round ? Math.round(value) : value;
        }
    }
    return out;
}

export function prepareImportedMask(args: {
    data: DrawingArray;
    sourceWidth: number;
    sourceHeight: number;
    destWidth: number;
    destHeight: number;
    sourceRepresentation: SegmentationDataRepresentation;
    destRepresentation: SegmentationDataRepresentation;
    sourceMatrix: number[][] | null | undefined;
    destMatrix: number[][] | null | undefined;
    threshold: number;
}): DrawingArray | null {
    const {
        data,
        sourceWidth,
        sourceHeight,
        destWidth,
        destHeight,
        sourceRepresentation,
        destRepresentation,
        sourceMatrix,
        destMatrix,
        threshold,
    } = args;

    let converted: DrawingArray | null = null;
    if (
        isSimpleRepresentation(sourceRepresentation) &&
        isSimpleRepresentation(destRepresentation)
    ) {
        converted = convert(
            data,
            sourceRepresentation,
            destRepresentation,
            threshold,
        );
    } else if (sourceRepresentation === destRepresentation) {
        converted = data;
    }
    if (!converted) return null;
    if (sourceMatrix == null && destMatrix == null) return converted;

    return resample(
        converted,
        sourceWidth,
        sourceHeight,
        destWidth,
        destHeight,
        sourceMatrix,
        destMatrix,
        destRepresentation === "Probability",
    );
}
