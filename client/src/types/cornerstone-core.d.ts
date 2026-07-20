declare module "cornerstone-core" {
    export interface CornerstonePixelDataElement {
        dataOffset: number;
        length: number;
    }

    export interface CornerstoneDataSet {
        byteArray: Uint8Array;
        elements: Record<string, CornerstonePixelDataElement>;
    }

    export interface CornerstoneImage {
        data: CornerstoneDataSet;
        getPixelData(): ArrayLike<number>;
    }

    export function loadImage(imageId: string): Promise<CornerstoneImage>;
    export const EVENTS: Record<string, string>;
    export function enable(element: HTMLElement): void;
    export function disable(element: HTMLElement): void;
    export function displayImage(
        element: HTMLElement,
        image: CornerstoneImage,
    ): void;
    export function reset(element: HTMLElement): void;
    export function resize(element: HTMLElement): void;
}

declare module "cornerstone-wado-image-loader" {
    import type * as Cornerstone from "cornerstone-core";
    import type * as DicomParser from "dicom-parser";

    export const external: {
        cornerstone: typeof Cornerstone;
        dicomParser: typeof DicomParser;
    };

    export function configure(config: {
        beforeSend?: (xhr: XMLHttpRequest) => void;
        useWebWorkers?: boolean;
        [key: string]: unknown;
    }): void;
}

declare module "dicom-parser" {
    import type { CornerstoneDataSet } from "cornerstone-core";

    export function parseDicom(byteArray: Uint8Array): DicomDataset;

    export function explicitDataSetToJS(
        dataSet: CornerstoneDataSet,
    ): Record<string, unknown>;

    interface DicomDataset {
        string(tag: string): string | undefined;
        uint16(tag: string): number | undefined;
        byteArray: Uint8Array;
        elements: Record<string, { dataOffset: number; length: number }>;
    }
}
