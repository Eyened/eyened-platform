/**
 * DICOM JPEG Baseline/Extended (.50 / .51) via the browser JPEG decoder.
 * 8-bit only. Returns mono (1 byte/px) or RGB (3 bytes/px).
 */
export async function decodeJpegBaselineFrame(
    compressed: Uint8Array,
    samplesPerPixel: number,
): Promise<Uint8Array> {
    const copy = new Uint8Array(
        compressed.buffer,
        compressed.byteOffset,
        compressed.byteLength,
    );
    const bitmap = await createImageBitmap(
        new Blob([copy], { type: "image/jpeg" }),
    );
    try {
        const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
        const ctx = canvas.getContext("2d");
        if (!ctx) {
            throw new Error("OffscreenCanvas 2d context unavailable");
        }
        ctx.drawImage(bitmap, 0, 0);
        const { data, width, height } = ctx.getImageData(
            0,
            0,
            bitmap.width,
            bitmap.height,
        );
        const n = width * height;
        if (samplesPerPixel >= 3) {
            const rgb = new Uint8Array(n * 3);
            for (let i = 0; i < n; i++) {
                rgb[i * 3] = data[i * 4];
                rgb[i * 3 + 1] = data[i * 4 + 1];
                rgb[i * 3 + 2] = data[i * 4 + 2];
            }
            return rgb;
        }
        const mono = new Uint8Array(n);
        for (let i = 0; i < n; i++) {
            mono[i] = data[i * 4];
        }
        return mono;
    } finally {
        bitmap.close();
    }
}
