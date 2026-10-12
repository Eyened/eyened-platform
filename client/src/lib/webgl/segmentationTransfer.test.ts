import { describe, expect, it } from "vitest";
import { prepareImportedMask } from "./segmentationTransfer";

const scale2 = [
    [2, 0, 0],
    [0, 2, 0],
    [0, 0, 1],
];

describe("prepareImportedMask", () => {
    it("copies the source buffer when neither matrix is set", () => {
        const result = prepareImportedMask({
            data: Uint8Array.from([1, 2, 3, 4]),
            sourceWidth: 2,
            sourceHeight: 2,
            destWidth: 8,
            destHeight: 8,
            sourceRepresentation: "Binary",
            destRepresentation: "Binary",
            sourceMatrix: null,
            destMatrix: null,
            threshold: 127,
        });

        expect(Array.from(result!)).toEqual([1, 2, 3, 4]);
    });

    it("warps a model grid onto the image with the source matrix", () => {
        const result = prepareImportedMask({
            data: Uint8Array.from([
                0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
            ]),
            sourceWidth: 4,
            sourceHeight: 4,
            destWidth: 8,
            destHeight: 8,
            sourceRepresentation: "Binary",
            destRepresentation: "Binary",
            sourceMatrix: scale2,
            destMatrix: null,
            threshold: 127,
        });

        expect(Array.from(result!)).toEqual([
            0, 0, 1, 2, 2, 2, 3, 0, 0, 0, 1, 2, 2, 2, 3, 0, 4, 4, 5, 6, 6, 6, 7,
            0, 8, 8, 9, 10, 10, 10, 11, 0, 8, 8, 9, 10, 10, 10, 11, 0, 8, 8, 9,
            10, 10, 10, 11, 0, 12, 12, 13, 14, 14, 14, 15, 0, 0, 0, 0, 0, 0, 0,
            0, 0,
        ]);
    });

    it("samples image-space data into a destination region matrix", () => {
        const result = prepareImportedMask({
            data: Uint8Array.from([
                0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
            ]),
            sourceWidth: 4,
            sourceHeight: 4,
            destWidth: 2,
            destHeight: 2,
            sourceRepresentation: "Binary",
            destRepresentation: "Binary",
            sourceMatrix: null,
            destMatrix: scale2,
            threshold: 127,
        });

        expect(Array.from(result!)).toEqual([0, 2, 8, 10]);
    });

    it("composes both matrices through image space", () => {
        const result = prepareImportedMask({
            data: Uint8Array.from([
                0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
            ]),
            sourceWidth: 4,
            sourceHeight: 4,
            destWidth: 2,
            destHeight: 2,
            sourceRepresentation: "Binary",
            destRepresentation: "Binary",
            sourceMatrix: scale2,
            destMatrix: [
                [2, 0, 2],
                [0, 2, 0],
                [0, 0, 1],
            ],
            threshold: 127,
        });

        expect(Array.from(result!)).toEqual([1, 2, 5, 6]);
    });

    it("leaves destination pixels empty when they fall outside the source", () => {
        const result = prepareImportedMask({
            data: Uint8Array.from([7, 7, 7, 7]),
            sourceWidth: 2,
            sourceHeight: 2,
            destWidth: 4,
            destHeight: 4,
            sourceRepresentation: "Binary",
            destRepresentation: "Binary",
            sourceMatrix: [
                [1, 0, 0],
                [0, 1, 0],
                [0, 0, 1],
            ],
            destMatrix: null,
            threshold: 127,
        });

        expect(Array.from(result!)).toEqual([
            7, 7, 0, 0, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        ]);
    });

    it("bilinear-samples probability masks", () => {
        const result = prepareImportedMask({
            data: Uint8Array.from([0, 64, 128, 255]),
            sourceWidth: 4,
            sourceHeight: 1,
            destWidth: 8,
            destHeight: 1,
            sourceRepresentation: "Probability",
            destRepresentation: "Probability",
            sourceMatrix: scale2,
            destMatrix: null,
            threshold: 127,
        });

        expect(Array.from(result!)).toEqual([
            0, 32, 64, 96, 128, 192, 255, 128,
        ]);
    });

    it("converts representation before resampling", () => {
        const result = prepareImportedMask({
            data: Uint8Array.from([0, 255]),
            sourceWidth: 2,
            sourceHeight: 1,
            destWidth: 4,
            destHeight: 1,
            sourceRepresentation: "Binary",
            destRepresentation: "Probability",
            sourceMatrix: scale2,
            destMatrix: null,
            threshold: 127,
        });

        expect(Array.from(result!)).toEqual([0, 128, 255, 128]);
    });

    it("returns null when the representations cannot be converted", () => {
        const result = prepareImportedMask({
            data: Uint8Array.from([1, 2, 3, 4]),
            sourceWidth: 2,
            sourceHeight: 2,
            destWidth: 2,
            destHeight: 2,
            sourceRepresentation: "MultiClass",
            destRepresentation: "Binary",
            sourceMatrix: scale2,
            destMatrix: null,
            threshold: 127,
        });

        expect(result).toBeNull();
    });
});
