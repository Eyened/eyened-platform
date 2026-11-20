import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
    TRANSFER_SYNTAX,
    decodeDicomBuffer,
    extractDimensions,
    type DecodeFrameFn,
} from "./dicomDecoder";

const fixtures = join(dirname(fileURLToPath(import.meta.url)), "fixtures");

function loadFixture(name: string): ArrayBuffer {
    const buf = readFileSync(join(fixtures, name));
    return Uint8Array.from(buf).buffer;
}

function flatFrames(values: number[], frameSize = 12): DecodeFrameFn {
    let call = 0;
    return async (frame) => {
        expect(frame.byteLength).toBeGreaterThan(0);
        const v = values[call++]!;
        return new Uint8Array(frameSize).fill(v);
    };
}

describe("decodeDicomBuffer", () => {
    it("decodes uncompressed multi-frame Explicit VR LE", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("uncompressed_2frames.dcm"),
        );
        expect(decoded.dimensions).toMatchObject({
            width: 4,
            height: 3,
            depth: 2,
        });
        expect(decoded.volume.length).toBe(4 * 3 * 2);
        expect(decoded.volume[0]).toBe(1);
        expect(decoded.volume[12]).toBe(20);
        expect(decoded.volume[23]).toBe(99);
        expect(decoded.photometricInterpretation).toBe("MONOCHROME2");
        expect(decoded.transferSyntax).toBe(
            TRANSFER_SYNTAX.ExplicitVRLittleEndian,
        );
    });

    it("drops the even-length pad on odd uncompressed frames", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("uncompressed_odd_padded.dcm"),
        );
        expect(decoded.volume.length).toBe(9);
        expect(decoded.volume[0]).toBe(7);
        expect(decoded.volume[8]).toBe(8);
    });

    it("truncates uncompressed 16-bit samples to the low byte", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("uncompressed_16bit.dcm"),
        );
        expect(decoded.volume.length).toBe(12);
        expect(decoded.volume[0]).toBe(0x2c);
        expect(decoded.volume[11]).toBe(0xff);
    });

    it("decodes JPEG Baseline (.50)", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("jpeg_baseline_2frames.dcm"),
            { decodeJpegLossy: flatFrames([11, 22]) },
        );
        expect(decoded.transferSyntax).toBe(TRANSFER_SYNTAX.JPEGBaseline);
        expect(decoded.volume[0]).toBe(11);
        expect(decoded.volume[12]).toBe(22);
    });

    it("decodes JPEG Extended (.51)", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("jpeg_extended_2frames.dcm"),
            { decodeJpegLossy: flatFrames([77, 88]) },
        );
        expect(decoded.transferSyntax).toBe(TRANSFER_SYNTAX.JPEGExtended);
        expect(decoded.volume[0]).toBe(77);
        expect(decoded.volume[12]).toBe(88);
    });

    it("decodes JPEG Lossless Process 14 (.57) with the lossless decoder", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("jpeg_lossless_2frames.dcm"),
            {
                forceTransferSyntax: TRANSFER_SYNTAX.JPEGLosslessP14,
                decodeJpegLossless: flatFrames([55, 66]),
            },
        );
        expect(decoded.transferSyntax).toBe(TRANSFER_SYNTAX.JPEGLosslessP14);
        expect(decoded.volume[0]).toBe(55);
        expect(decoded.volume[12]).toBe(66);
    });

    it("decodes JPEG Lossless (.70)", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("jpeg_lossless_2frames.dcm"),
            { decodeJpegLossless: flatFrames([55, 66]) },
        );
        expect(decoded.transferSyntax).toBe(TRANSFER_SYNTAX.JPEGLossless);
        expect(decoded.volume[0]).toBe(55);
        expect(decoded.volume[12]).toBe(66);
    });

    it("decodes JPEG 2000 (.91)", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("j2k_2frames.dcm"),
            {
                decodeJ2k: flatFrames([33, 44]),
            },
        );
        expect(decoded.transferSyntax).toBe(TRANSFER_SYNTAX.JPEG2000);
        expect(decoded.volume[0]).toBe(33);
        expect(decoded.volume[12]).toBe(44);
    });

    it("rejects unsupported transfer syntax", async () => {
        await expect(
            decodeDicomBuffer(loadFixture("uncompressed_2frames.dcm"), {
                forceTransferSyntax: "1.2.840.10008.1.2.4.80",
            }),
        ).rejects.toThrow(/unsupported transfer syntax/i);
    });

    it("decodes JPEG Lossless with the real codec", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("jpeg_lossless_2frames.dcm"),
        );
        expect(decoded.volume.length).toBe(24);
        expect(decoded.volume[0]).toBe(55);
        expect(decoded.volume[12]).toBe(66);
    });

    it("decodes JPEG Lossless when the basic offset table is empty", async () => {
        const decoded = await decodeDicomBuffer(
            loadFixture("jpeg_lossless_2frames_empty_bot.dcm"),
        );
        expect(decoded.transferSyntax).toBe(TRANSFER_SYNTAX.JPEGLossless);
        expect(decoded.volume.length).toBe(24);
        expect(decoded.volume[0]).toBe(55);
        expect(decoded.volume[12]).toBe(66);
    });

    it("rejects a frame whose decoded length does not match", async () => {
        await expect(
            decodeDicomBuffer(loadFixture("jpeg_baseline_2frames.dcm"), {
                decodeJpegLossy: async () => new Uint8Array(1),
            }),
        ).rejects.toThrow(/length 1/);
    });

    it("reads shared functional group spacing and ignores a bad group", () => {
        const shared = extractDimensions({
            x00280011: 4,
            x00280010: 3,
            x00280008: 2,
            x52009229: [
                { x00289110: [{ x00280030: "0.1\\0.2", x00180050: "0.3" }] },
            ],
        });
        expect(shared.width_mm).toBeCloseTo(0.8);
        expect(shared.depth_mm).toBeCloseTo(0.6);
        const broken = extractDimensions({
            x00280011: 4,
            x00280010: 3,
            x00280008: 2,
            x52009229: "nope",
        });
        expect(broken.depth_mm).toBe(-2);
    });

    it("decodes JPEG 2000 with the real OpenJPEG codec", async () => {
        const decoded = await decodeDicomBuffer(loadFixture("j2k_2frames.dcm"));
        expect(decoded.volume.length).toBe(24);
        expect(decoded.volume[0]).toBe(33);
        expect(decoded.volume[12]).toBe(44);
        const file = readFileSync(join(fixtures, "j2k_2frames.dcm"));
        const soc = file.indexOf(Buffer.from([0xff, 0x4f]));
        const jp = file.indexOf(Buffer.from("jP  "));
        expect(soc).toBeGreaterThan(0);
        expect(jp).toBe(-1);
    });
});
