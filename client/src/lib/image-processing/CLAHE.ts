// CLAHE implementation in TypeScript
export class CLAHE {
    private clipLimit: number;
    private tileSize: number;

    constructor(tileSize = 32, clipLimit = 40) {
        this.tileSize = tileSize; // Size of tiles
        this.clipLimit = clipLimit; // Clip limit for histogram
    }

    public applyClahe(data: Uint8ClampedArray, width: number, height: number): Uint8ClampedArray {
        const tileWidth = Math.ceil(width / this.tileSize);
        const tileHeight = Math.ceil(height / this.tileSize);

        // Step 1: Compute histograms for each tile
        const histograms: Uint32Array[][] = [];
        for (let ty = 0; ty < this.tileSize; ty++) {
            histograms[ty] = [];
            for (let tx = 0; tx < this.tileSize; tx++) {
                histograms[ty][tx] = this.computeHistogram(data, width, height, tx, ty, tileWidth, tileHeight);
                this.clipHistogram(histograms[ty][tx]);
            }
        }

        // Step 2: Compute cumulative distribution function (CDF) for each histogram
        const cdfs: Uint8ClampedArray[][] = histograms.map(row => row.map(hist => this.computeCdf(hist)));

        // Step 3: Apply interpolation and remap pixel values
        const output = new Uint8ClampedArray(data.length);
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                output[y * width + x] = this.interpolate(x, y, width, height, data, cdfs, tileWidth, tileHeight);
            }
        }

        return output;
    }

    private computeHistogram(data: Uint8ClampedArray, width: number, height: number, tx: number, ty: number, tileWidth: number, tileHeight: number): Uint32Array {
        const hist = new Uint32Array(256);
        const startX = tx * tileWidth;
        const startY = ty * tileHeight;
        const endX = Math.min(startX + tileWidth, width);
        const endY = Math.min(startY + tileHeight, height);

        for (let y = startY; y < endY; y++) {
            for (let x = startX; x < endX; x++) {
                hist[data[y * width + x]]++;
            }
        }

        return hist;
    }

    private clipHistogram(hist: Uint32Array): void {
        const excess = hist.reduce((sum, count) => sum + Math.max(0, count - this.clipLimit), 0);
        const distribute = Math.floor(excess / 256);
        const remainder = excess % 256;

        for (let i = 0; i < hist.length; i++) {
            if (hist[i] > this.clipLimit) {
                hist[i] = this.clipLimit;
            }
            hist[i] += distribute;
        }

        for (let i = 0; i < remainder; i++) {
            hist[i % 256]++;
        }
    }

    private computeCdf(hist: Uint32Array): Uint8ClampedArray {
        const cdf = new Uint8ClampedArray(256);
        let cumulative = 0;
        const total = hist.reduce((sum, count) => sum + count, 0);

        for (let i = 0; i < hist.length; i++) {
            cumulative += hist[i];
            cdf[i] = Math.round((cumulative / total) * 255);
        }

        return cdf;
    }

    private interpolate(x: number, y: number, width: number, height: number, data: Uint8ClampedArray, cdfs: Uint8ClampedArray[][], tileWidth: number, tileHeight: number): number {
        const fx = x / tileWidth - 0.5;
        const fy = y / tileHeight - 0.5;

        const tx1 = Math.max(Math.floor(fx), 0);
        const ty1 = Math.max(Math.floor(fy), 0);
        const tx2 = Math.min(tx1 + 1, this.tileSize - 1);
        const ty2 = Math.min(ty1 + 1, this.tileSize - 1);

        const dx = fx - tx1;
        const dy = fy - ty1;

        const v00 = cdfs[ty1][tx1][data[y * width + x]];
        const v10 = cdfs[ty1][tx2][data[y * width + x]];
        const v01 = cdfs[ty2][tx1][data[y * width + x]];
        const v11 = cdfs[ty2][tx2][data[y * width + x]];

        return Math.round(
            (1 - dx) * (1 - dy) * v00 +
            dx * (1 - dy) * v10 +
            (1 - dx) * dy * v01 +
            dx * dy * v11
        );
    }

    // Convert RGB to HSL (with L in range [0, 255])
    public rgbToHsl(r: number, g: number, b: number): { h: number; s: number; l: number } {
        r /= 255;
        g /= 255;
        b /= 255;

        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        const l = ((max + min) / 2) * 255;

        let h = 0;
        let s = 0;

        if (max !== min) {
            const d = max - min;
            s = l > 127.5 ? d / (2 - max - min) : d / (max + min);

            switch (max) {
                case r:
                    h = (g - b) / d + (g < b ? 6 : 0);
                    break;
                case g:
                    h = (b - r) / d + 2;
                    break;
                case b:
                    h = (r - g) / d + 4;
                    break;
            }

            h /= 6;
        }

        return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l) };
    }

    // Convert HSL (with L in range [0, 255]) to RGB
    public hslToRgb(h: number, s: number, l: number): { r: number; g: number; b: number } {
        l /= 255;
        s /= 100;
        h /= 360;

        const hueToRgb = (p: number, q: number, t: number): number => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1 / 6) return p + (q - p) * 6 * t;
            if (t < 1 / 2) return q;
            if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
            return p;
        };

        let r: number, g: number, b: number;

        if (s === 0) {
            r = g = b = l; // achromatic
        } else {
            const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            const p = 2 * l - q;
            r = hueToRgb(p, q, h + 1 / 3);
            g = hueToRgb(p, q, h);
            b = hueToRgb(p, q, h - 1 / 3);
        }

        return {
            r: Math.round(r * 255),
            g: Math.round(g * 255),
            b: Math.round(b * 255),
        };
    }
}
