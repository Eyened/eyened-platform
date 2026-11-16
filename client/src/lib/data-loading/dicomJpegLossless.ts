import { Decoder } from "jpeg-lossless-decoder-js";

/**
 * DICOM JPEG Lossless (1.2.840.10008.1.2.4.70).
 * Returns unsigned 8-bit samples (16-bit values truncated like the old
 * `Uint8Array.from(getPixelData())` path).
 */
export async function decodeJpegLosslessFrame(
    compressed: Uint8Array,
    bitsAllocated: number,
): Promise<Uint8Array> {
    const decoder = new Decoder();
    const byteOutput = bitsAllocated <= 8 ? 1 : 2;
    const decompressed = decoder.decode(
        compressed.buffer as ArrayBuffer,
        compressed.byteOffset,
        compressed.byteLength,
        byteOutput,
    ) as Uint8Array | Uint16Array;

    if (decompressed instanceof Uint8Array) {
        return new Uint8Array(decompressed);
    }
    return Uint8Array.from(decompressed);
}
