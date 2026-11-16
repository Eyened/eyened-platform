/**
 * JPEG 2000 frame decode via OpenJPEG WASM (same codec CWIL used).
 */
import openJpegFactory from "@cornerstonejs/codec-openjpeg/decodewasmjs";
import openjpegWasmUrl from "@cornerstonejs/codec-openjpeg/decodewasm?url";

type J2KDecoder = {
    getEncodedBuffer: (length: number) => Uint8Array;
    decode: () => void;
    getFrameInfo: () => {
        width: number;
        height: number;
        bitsPerSample: number;
        componentCount: number;
        isSigned: boolean;
    };
    getDecodedBuffer: () => Uint8Array;
};

type OpenJpegModule = {
    J2KDecoder: new () => J2KDecoder;
};

let decoderPromise: Promise<J2KDecoder> | undefined;

/**
 * Vite `?url` is root-relative (`/node_modules/...`). In the browser that is an
 * HTTP path; in Node/Vitest Emscripten opens it with fs, so prefix cwd.
 */
function resolveWasmLocatePath(file: string): string {
    if (!file.endsWith(".wasm")) {
        return file;
    }
    const url = openjpegWasmUrl;
    if (url.startsWith("file:") || /^https?:/i.test(url)) {
        return url;
    }
    const isNode =
        typeof process !== "undefined" &&
        Boolean(process.versions && process.versions.node);
    if (isNode && url.startsWith("/")) {
        return `${process.cwd()}${url}`;
    }
    return url;
}

async function getDecoder(): Promise<J2KDecoder> {
    if (!decoderPromise) {
        decoderPromise = (async () => {
            const factory = openJpegFactory as (opts: {
                locateFile: (f: string) => string;
            }) => Promise<OpenJpegModule>;
            const instance = await factory({
                locateFile: resolveWasmLocatePath,
            });
            return new instance.J2KDecoder();
        })();
    }
    return decoderPromise;
}

/** Decode one encapsulated J2K codestream to unsigned 8-bit samples. */
export async function decodeJ2kFrame(
    compressed: Uint8Array,
): Promise<Uint8Array> {
    const decoder = await getDecoder();
    const encoded = decoder.getEncodedBuffer(compressed.length);
    encoded.set(compressed);
    decoder.decode();
    const frameInfo = decoder.getFrameInfo();
    const decoded = decoder.getDecodedBuffer();

    if (frameInfo.bitsPerSample > 8) {
        const src = frameInfo.isSigned
            ? new Int16Array(
                  decoded.buffer,
                  decoded.byteOffset,
                  decoded.byteLength / 2,
              )
            : new Uint16Array(
                  decoded.buffer,
                  decoded.byteOffset,
                  decoded.byteLength / 2,
              );
        return Uint8Array.from(src as unknown as ArrayLike<number>);
    }

    return new Uint8Array(decoded);
}
