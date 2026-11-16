declare module "dicom-parser" {
    export type ByteArray = Uint8Array | Buffer;

    export interface Fragment {
        offset: number;
        position: number;
        length: number;
    }

    export interface Element {
        tag: string;
        vr?: string;
        length: number;
        dataOffset: number;
        items?: Element[];
        encapsulatedPixelData?: boolean;
        basicOffsetTable?: number[];
        fragments?: Fragment[];
    }

    export interface DataSet {
        byteArray: ByteArray;
        elements: { [tag: string]: Element };
        warnings: string[];
        uint16: (tag: string, index?: number) => number | undefined;
        string: (tag: string, index?: number) => string | undefined;
    }

    export function parseDicom(arr: Uint8Array): DataSet;
    export function explicitDataSetToJS(
        dataSet: DataSet,
        options?: { omitPrivateAttibutes?: boolean; maxElementLength?: number },
    ): unknown;
    export function readEncapsulatedImageFrame(
        dataSet: DataSet,
        pixelDataElement: Element,
        frameIndex: number,
        basicOffsetTable?: number[],
        fragments?: Fragment[],
    ): ByteArray;
}

declare module "jpeg-lossless-decoder-js" {
    export class Decoder {
        constructor(buffer?: ArrayBuffer | null, numBytes?: number);
        decode(
            buffer: ArrayBuffer,
            offset: number,
            length: number,
            numBytes?: number,
        ): Uint8Array | Uint16Array;
    }
}

declare module "@cornerstonejs/codec-openjpeg/decodewasmjs" {
    const factory: (opts?: { locateFile?: (f: string) => string }) => Promise<{
        J2KDecoder: new () => {
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
    }>;
    export default factory;
}

declare module "@cornerstonejs/codec-openjpeg/decodewasm?url" {
    const url: string;
    export default url;
}
