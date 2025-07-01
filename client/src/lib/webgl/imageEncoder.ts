import type { Serializer } from "./drawingHistory";
import type { DrawingArray } from "./segmentation";


/**
 * Serialises a single-channel image (R8/R16/R32) into a lossless PNG data-URL
 * and deserialises it back again.
 *
 * Per-pixel layout in the PNG is:
 *   - byte 0 … byte nBytes-1  → the actual value
 *   - remaining channels      → left at 255 for full opacity
 */
export class Base64Serializer implements Serializer<string> {
    private readonly canvas: HTMLCanvasElement;
    private readonly ctx: CanvasRenderingContext2D;
    private readonly nBytes: number;

    constructor(
        private readonly dataType: "R8" | "R8UI" | "R16UI" | "R32UI" | "R32F",
        private readonly width: number,
        private readonly height: number
    ) {
        this.canvas = document.createElement("canvas");
        this.canvas.width = width;
        this.canvas.height = height;
        this.ctx = this.canvas.getContext("2d")!;

        this.nBytes = {
            R8: 1,
            R8UI: 1,
            R16UI: 2,
            R32UI: 4,
            R32F: 4
        }[this.dataType];
    }

    serialize(data: DrawingArray): string {
        // Treat the input data as raw bytes
        const byteView = new Uint8Array(data.buffer);

        const img = this.ctx.createImageData(this.width, this.height);
        const out = img.data; // RGBA byte buffer

        const pixels = this.width * this.height;
        for (let i = 0; i < pixels; i++) {
            const baseOut = i * 4; // RGBA stride
            const baseIn = i * this.nBytes;

            // copy nBytes of the value
            for (let j = 0; j < this.nBytes; j++) {
                out[baseOut + j] = byteView[baseIn + j];
            }

            // fill unused channels (keeps the PNG opaque / fully specified)
            for (let j = this.nBytes; j < 4; j++) {
                out[baseOut + j] = 255;
            }
        }

        this.ctx.putImageData(img, 0, 0);
        return this.canvas.toDataURL("image/png");
    }

    deserialize(dataURL: string): Promise<DrawingArray> {
        const img = new Image();
        img.src = dataURL;

        return new Promise<DrawingArray>((resolve, reject) => {
            img.onerror = () =>
                reject(new Error("Failed to load image for deserialisation"));

            img.onload = () => {
                this.ctx.drawImage(img, 0, 0);
                const rgba = this.ctx.getImageData(0, 0, this.width, this.height).data;
                const buffer = new ArrayBuffer(this.width * this.height * this.nBytes);
                const byteView = new Uint8Array(buffer);

                const pixels = this.width * this.height;
                for (let i = 0; i < pixels; i++) {
                    const baseIn = i * 4; // RGBA stride
                    const baseOut = i * this.nBytes;
                    for (let j = 0; j < this.nBytes; j++) {
                        byteView[baseOut + j] = rgba[baseIn + j];
                    }
                }
                // Return the correctly-typed view on the buffer
                switch (this.dataType) {
                    case "R8UI":
                    case "R8":
                        resolve(new Uint8Array(buffer));
                        break;
                    case "R16UI":
                        resolve(new Uint16Array(buffer));
                        break;
                    case "R32UI":
                        resolve(new Uint32Array(buffer));
                        break;
                    case "R32F":
                        resolve(new Float32Array(buffer));
                        break;
                }
            };
        });
    }
}
