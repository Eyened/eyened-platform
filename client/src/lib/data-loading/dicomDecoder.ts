import type { Dimensions } from "$lib/webgl/types";
import * as dicomParser from "dicom-parser";
import { decodeJ2kFrame } from "./dicomJ2k";
import { decodeJpegBaselineFrame } from "./dicomJpegBaseline";
import { decodeJpegLosslessFrame } from "./dicomJpegLossless";
import { dicomDecodeConcurrency, mapPool } from "./mapPool";

/** Transfer syntaxes we decode client-side (plus uncompressed LE). */
export const TRANSFER_SYNTAX = {
    ImplicitVRLittleEndian: "1.2.840.10008.1.2",
    ExplicitVRLittleEndian: "1.2.840.10008.1.2.1",
    JPEGBaseline: "1.2.840.10008.1.2.4.50",
    JPEGExtended: "1.2.840.10008.1.2.4.51",
    JPEGLossless: "1.2.840.10008.1.2.4.70",
    JPEG2000Lossless: "1.2.840.10008.1.2.4.90",
    JPEG2000: "1.2.840.10008.1.2.4.91",
} as const;

const UNCOMPRESSED = new Set<string>([
    TRANSFER_SYNTAX.ImplicitVRLittleEndian,
    TRANSFER_SYNTAX.ExplicitVRLittleEndian,
]);

/** Lossy JPEG via browser decoder (8-bit). */
const JPEG_LOSSY = new Set<string>([
    TRANSFER_SYNTAX.JPEGBaseline,
    TRANSFER_SYNTAX.JPEGExtended,
]);

const JPEG_LOSSLESS = new Set<string>([TRANSFER_SYNTAX.JPEGLossless]);

const JPEG2000 = new Set<string>([
    TRANSFER_SYNTAX.JPEG2000Lossless,
    TRANSFER_SYNTAX.JPEG2000,
]);

export type DecodeFrameFn = (frame: Uint8Array) => Promise<Uint8Array>;

export type DecodeDicomOptions = {
    concurrency?: number;
    logId?: string;
    decodeJ2k?: DecodeFrameFn;
    decodeJpegLossy?: DecodeFrameFn;
    decodeJpegLossless?: DecodeFrameFn;
    /** Test-only: override transfer syntax after parse. */
    forceTransferSyntax?: string;
};

export type DecodedDicom = {
    volume: Uint8Array;
    dimensions: Dimensions;
    meta: Record<string, unknown>;
    photometricInterpretation?: string;
    transferSyntax: string;
};

export async function decodeDicomBuffer(
    buffer: ArrayBuffer,
    options: DecodeDicomOptions = {},
): Promise<DecodedDicom> {
    const byteArray = new Uint8Array(buffer);
    const dataSet = dicomParser.parseDicom(byteArray);
    const meta = dicomParser.explicitDataSetToJS(dataSet) as Record<
        string,
        unknown
    >;
    const transferSyntax =
        options.forceTransferSyntax ??
        dataSet.string("x00020010") ??
        String(meta.x00020010 ?? "");
    const dimensions = extractDimensions(meta);
    const photometricInterpretation = dataSet.string("x00280004");
    const samplesPerPixel = dataSet.uint16("x00280002") ?? 1;
    const bitsAllocated = dataSet.uint16("x00280100") ?? 8;
    const { width, height, depth } = dimensions;
    const pixelElement = dataSet.elements.x7fe00010;
    if (!pixelElement) {
        throw new Error("DICOM missing PixelData (7FE0,0010)");
    }

    const logId = options.logId ?? "?";

    if (UNCOMPRESSED.has(transferSyntax)) {
        const monoExpected = width * height * depth;
        const expected =
            monoExpected * samplesPerPixel * bytesPerSample(bitsAllocated);
        if (
            pixelElement.length === expected ||
            pixelElement.length === monoExpected
        ) {
            console.info(
                `[dicomDecoder] ${logId}: uncompressed ${width}x${height}x${depth} ` +
                    `(transferSyntax=${transferSyntax})`,
            );
            const volume = toUint8(
                dataSet.byteArray.subarray(
                    pixelElement.dataOffset,
                    pixelElement.dataOffset + pixelElement.length,
                ),
            );
            return {
                volume,
                dimensions,
                meta,
                photometricInterpretation,
                transferSyntax,
            };
        }
        throw new Error(
            `Uncompressed PixelData length ${pixelElement.length} != expected ${expected}`,
        );
    }

    if (JPEG_LOSSY.has(transferSyntax)) {
        if (bitsAllocated > 8) {
            throw new Error(
                `JPEG Baseline/Extended with bitsAllocated=${bitsAllocated} ` +
                    `is not supported (need 8-bit); transferSyntax=${transferSyntax}`,
            );
        }
        const channels = samplesPerPixel >= 3 ? 3 : 1;
        const frameSize = width * height * channels;
        const decode =
            options.decodeJpegLossy ??
            ((frame) => decodeJpegBaselineFrame(frame, samplesPerPixel));
        console.info(
            `[dicomDecoder] ${logId}: JPEG lossy ${depth} frame(s) ` +
                `${width}x${height} (transferSyntax=${transferSyntax})`,
        );
        const volume = await decodeEncapsulatedFrames(
            dataSet,
            pixelElement,
            depth,
            frameSize,
            decode,
            options.concurrency,
        );
        return {
            volume,
            dimensions,
            meta,
            photometricInterpretation,
            transferSyntax,
        };
    }

    if (JPEG_LOSSLESS.has(transferSyntax)) {
        const frameSize = width * height * samplesPerPixel;
        const decode =
            options.decodeJpegLossless ??
            ((frame) => decodeJpegLosslessFrame(frame, bitsAllocated));
        console.info(
            `[dicomDecoder] ${logId}: JPEG lossless ${depth} frame(s) ` +
                `${width}x${height} (transferSyntax=${transferSyntax})`,
        );
        const volume = await decodeEncapsulatedFrames(
            dataSet,
            pixelElement,
            depth,
            frameSize,
            decode,
            options.concurrency,
        );
        return {
            volume,
            dimensions,
            meta,
            photometricInterpretation,
            transferSyntax,
        };
    }

    if (JPEG2000.has(transferSyntax)) {
        const frameSize = width * height * samplesPerPixel;
        const decode = options.decodeJ2k ?? decodeJ2kFrame;
        console.info(
            `[dicomDecoder] ${logId}: JPEG 2000 ${depth} frame(s) ` +
                `${width}x${height} (transferSyntax=${transferSyntax})`,
        );
        const volume = await decodeEncapsulatedFrames(
            dataSet,
            pixelElement,
            depth,
            frameSize,
            decode,
            options.concurrency,
        );
        return {
            volume,
            dimensions,
            meta,
            photometricInterpretation,
            transferSyntax,
        };
    }

    throw new Error(`Unsupported transfer syntax: ${transferSyntax}`);
}

async function decodeEncapsulatedFrames(
    dataSet: dicomParser.DataSet,
    pixelElement: dicomParser.Element,
    depth: number,
    frameSize: number,
    decodeFrame: DecodeFrameFn,
    concurrency?: number,
): Promise<Uint8Array> {
    const volume = new Uint8Array(frameSize * depth);
    const indices = Array.from({ length: depth }, (_, i) => i);
    const limit = concurrency ?? dicomDecodeConcurrency();
    await mapPool(indices, limit, async (frameIndex) => {
        const compressed = dicomParser.readEncapsulatedImageFrame(
            dataSet,
            pixelElement,
            frameIndex,
        );
        const frame = await decodeFrame(toUint8(compressed));
        if (frame.length !== frameSize) {
            throw new Error(
                `Frame ${frameIndex} length ${frame.length} != ${frameSize}`,
            );
        }
        volume.set(frame, frameIndex * frameSize);
    });
    return volume;
}

function bytesPerSample(bitsAllocated: number): number {
    return bitsAllocated > 8 ? 2 : 1;
}

function toUint8(bytes: Uint8Array | dicomParser.ByteArray): Uint8Array {
    return bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
}

/** Pixel spacing / size helpers shared with the previous cornerstone path. */
export function extractDimensions(meta: Record<string, unknown>): Dimensions {
    const width = Number(meta.x00280011);
    const height = Number(meta.x00280010);
    const depth = Number(meta.x00280008) || 1;

    let res_w = -1,
        res_h = -1,
        res_d = -1;

    const pixelSpacingRaw = meta.x00280030;
    if (typeof pixelSpacingRaw === "string") {
        const pixelSpacing = pixelSpacingRaw.split("\\").map(Number);
        [res_h, res_w] = pixelSpacing;
    }

    try {
        const shared = meta.x52009229 as
            | Array<{ x00289110: Array<Record<string, string>> }>
            | undefined;
        const resolutions = shared?.[0]?.x00289110?.[0];
        if (resolutions?.x00280030) {
            [res_h, res_w] = resolutions.x00280030.split("\\").map(Number);
            res_d = Number(resolutions.x00180050);
        }
    } catch (e) {
        if (depth > 1) {
            console.warn("No depth resolution found in DICOM metadata:", e);
        }
    }

    return {
        width,
        height,
        depth,
        width_mm: width * res_w,
        height_mm: height * res_h,
        depth_mm: depth * res_d,
    };
}
