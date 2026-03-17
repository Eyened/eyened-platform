import type { ImageGET } from '../../types/openapi_types';
import type { Dimensions } from '$lib/webgl/types';

type DataUrlBuilder = (
    imageId: string,
    query?: Record<string, string | number | boolean | undefined>
) => string;

type MhdElementType =
    | 'MET_CHAR'
    | 'MET_UCHAR'
    | 'MET_SHORT'
    | 'MET_USHORT'
    | 'MET_INT'
    | 'MET_UINT'
    | 'MET_FLOAT'
    | 'MET_DOUBLE';

export interface ParsedMhdHeader {
    ndims: number;
    dimSize: number[];
    spacing: number[];
    elementType: MhdElementType;
    channels: number;
    byteOrderMsb: boolean;
}

export interface LoadedMhdRawData {
    pixelData: Uint8Array;
    dimensions: Dimensions;
    meta: ParsedMhdHeader;
}

export async function loadMhdRawFromEndpoints(
    instance: ImageGET,
    imageId: string,
    buildDataUrl: DataUrlBuilder
): Promise<LoadedMhdRawData> {
    const mhdUrl = buildDataUrl(imageId, { meta: true });
    const rawUrl = buildDataUrl(imageId);

    const [mhdResponse, rawResponse] = await Promise.all([fetch(mhdUrl), fetch(rawUrl)]);
    if (!mhdResponse.ok) {
        throw new Error(`Failed to load mhd metadata (${mhdResponse.status})`);
    }
    if (!rawResponse.ok) {
        throw new Error(`Failed to load raw payload (${rawResponse.status})`);
    }

    const mhdText = await mhdResponse.text();
    const rawBuffer = await rawResponse.arrayBuffer();
    const header = parseMhdHeader(mhdText);

    const width = header.dimSize[0] ?? instance.columns;
    const height = header.dimSize[1] ?? instance.rows;
    const depth = header.dimSize[2] ?? 1;
    if (!width || !height || !depth) {
        throw new Error('Invalid MHD dimensions');
    }

    const voxelCount = width * height * depth * header.channels;
    const pixelData = convertRawToUint8(rawBuffer, header, voxelCount);

    const sx = header.spacing[0] ?? instance.resolution_horizontal ?? -1;
    const sy = header.spacing[1] ?? instance.resolution_axial ?? -1;
    const sz = header.spacing[2] ?? instance.resolution_vertical ?? -1;

    return {
        pixelData,
        dimensions: {
            width,
            height,
            depth,
            width_mm: sx > 0 ? sx * width : -1,
            height_mm: sy > 0 ? sy * height : -1,
            depth_mm: sz > 0 ? sz * depth : -1
        },
        meta: header
    };
}

function parseMhdHeader(mhdText: string): ParsedMhdHeader {
    const values = new Map<string, string>();

    for (const rawLine of mhdText.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line || line.startsWith('#')) {
            continue;
        }
        const separator = line.indexOf('=');
        if (separator < 0) {
            continue;
        }
        const key = line.slice(0, separator).trim();
        const value = line.slice(separator + 1).trim();
        values.set(key, value);
    }

    const ndims = Number(values.get('NDims') ?? 3);
    const dimSize = toNumberArray(values.get('DimSize'));
    const spacing = toNumberArray(values.get('ElementSpacing') ?? values.get('ElementSize'));
    const channels = Number(values.get('ElementNumberOfChannels') ?? 1);

    const rawElementType = values.get('ElementType') ?? 'MET_UCHAR';
    if (!isSupportedElementType(rawElementType)) {
        throw new Error(`Unsupported MHD ElementType: ${rawElementType}`);
    }

    const byteOrderField = values.get('BinaryDataByteOrderMSB') ?? values.get('ElementByteOrderMSB');
    const byteOrderMsb = byteOrderField === 'True' || byteOrderField === 'true' || byteOrderField === '1';

    if (dimSize.length < 2) {
        throw new Error('Invalid MHD header: DimSize must contain at least 2 values');
    }
    if (!Number.isFinite(channels) || channels < 1) {
        throw new Error('Invalid MHD header: ElementNumberOfChannels must be >= 1');
    }

    return {
        ndims,
        dimSize,
        spacing,
        elementType: rawElementType,
        channels,
        byteOrderMsb
    };
}

function toNumberArray(raw: string | undefined): number[] {
    if (!raw) {
        return [];
    }
    return raw
        .split(/\s+/)
        .filter((part) => part.length > 0)
        .map((part) => Number(part))
        .filter((value) => Number.isFinite(value));
}

function isSupportedElementType(value: string): value is MhdElementType {
    return (
        value === 'MET_CHAR' ||
        value === 'MET_UCHAR' ||
        value === 'MET_SHORT' ||
        value === 'MET_USHORT' ||
        value === 'MET_INT' ||
        value === 'MET_UINT' ||
        value === 'MET_FLOAT' ||
        value === 'MET_DOUBLE'
    );
}

function convertRawToUint8(buffer: ArrayBuffer, header: ParsedMhdHeader, voxelCount: number): Uint8Array {
    const bytesPerVoxel = bytesPerElement(header.elementType);
    const expectedBytes = voxelCount * bytesPerVoxel;
    if (buffer.byteLength < expectedBytes) {
        throw new Error(`RAW payload too small (${buffer.byteLength} < ${expectedBytes})`);
    }

    if (header.elementType === 'MET_UCHAR') {
        return new Uint8Array(buffer, 0, voxelCount);
    }

    const littleEndian = !header.byteOrderMsb;
    const view = new DataView(buffer, 0, expectedBytes);
    const values = new Float32Array(voxelCount);

    for (let i = 0; i < voxelCount; i++) {
        const offset = i * bytesPerVoxel;
        values[i] = readElementValue(view, offset, littleEndian, header.elementType);
    }

    return normalizeToUint8(values);
}

function bytesPerElement(elementType: MhdElementType): number {
    switch (elementType) {
        case 'MET_CHAR':
        case 'MET_UCHAR':
            return 1;
        case 'MET_SHORT':
        case 'MET_USHORT':
            return 2;
        case 'MET_INT':
        case 'MET_UINT':
        case 'MET_FLOAT':
            return 4;
        case 'MET_DOUBLE':
            return 8;
    }
}

function readElementValue(
    view: DataView,
    offset: number,
    littleEndian: boolean,
    elementType: MhdElementType
): number {
    switch (elementType) {
        case 'MET_CHAR':
            return view.getInt8(offset);
        case 'MET_UCHAR':
            return view.getUint8(offset);
        case 'MET_SHORT':
            return view.getInt16(offset, littleEndian);
        case 'MET_USHORT':
            return view.getUint16(offset, littleEndian);
        case 'MET_INT':
            return view.getInt32(offset, littleEndian);
        case 'MET_UINT':
            return view.getUint32(offset, littleEndian);
        case 'MET_FLOAT':
            return view.getFloat32(offset, littleEndian);
        case 'MET_DOUBLE':
            return view.getFloat64(offset, littleEndian);
    }
}

function normalizeToUint8(values: Float32Array): Uint8Array {
    if (values.length === 0) {
        return new Uint8Array();
    }

    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (let i = 0; i < values.length; i++) {
        const v = values[i];
        if (v < min) min = v;
        if (v > max) max = v;
    }

    if (!Number.isFinite(min) || !Number.isFinite(max)) {
        return new Uint8Array(values.length);
    }
    if (max === min) {
        return new Uint8Array(values.length);
    }

    const scale = 255 / (max - min);
    const out = new Uint8Array(values.length);
    for (let i = 0; i < values.length; i++) {
        const mapped = Math.round((values[i] - min) * scale);
        out[i] = clampByte(mapped);
    }
    return out;
}

function clampByte(value: number): number {
    if (value < 0) return 0;
    if (value > 255) return 255;
    return value;
}
