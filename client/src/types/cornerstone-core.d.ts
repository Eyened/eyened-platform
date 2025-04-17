declare module 'cornerstone-core' {
    export function loadImage(imageId: string): Promise<any>;
    // Add other functions you use
    export const EVENTS: any;
    export function enable(element: HTMLElement): void;
    export function disable(element: HTMLElement): void;
    export function displayImage(element: HTMLElement, image: any): void;
    export function reset(element: HTMLElement): void;
    export function resize(element: HTMLElement): void;
}

declare module 'cornerstone-wado-image-loader' {
    export const external: {
        cornerstone: any;
        dicomParser: any;

    };
    export function configure(config: {
        beforeSend?: (xhr: XMLHttpRequest) => void;
        [key: string]: any;
    }): void;

}

declare module 'dicom-parser' {
    export function parseDicom(byteArray: Uint8Array): DicomDataset;

    interface DicomDataset {
        string(tag: string): string | undefined;
        uint16(tag: string): number | undefined;
    }
}