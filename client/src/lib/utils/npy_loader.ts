type TypedArray =
    | Uint8Array
    | Int8Array
    | Uint16Array
    | Int16Array
    | Uint32Array
    | Int32Array
    | Float32Array
    | Float64Array;

// Map TypedArray constructor to numpy dtype string
const DTYPE_MAP = new Map<Function, string>([
    [Uint8Array, '|u1'],
    [Int8Array, '|i1'],
    [Uint16Array, '<u2'],
    [Int16Array, '<i2'],
    [Uint32Array, '<u4'],
    [Int32Array, '<i4'],
    [Float32Array, '<f4'],
    [Float64Array, '<f8'],
]);

// Reverse map from dtype string to TypedArray constructor
const DTYPE_REVERSE_MAP = new Map<string, any>([
    ['|u1', Uint8Array],
    ['|i1', Int8Array],
    ['<u2', Uint16Array],
    ['<i2', Int16Array],
    ['<u4', Uint32Array],
    ['<i4', Int32Array],
    ['<f4', Float32Array],
    ['<f8', Float64Array],
]);

// Encode TypedArray + shape into .npy ArrayBuffer
export function encodeNpy(
    data: TypedArray,
    shape: number[],
    version: 1 | 2 = 1,
    fortranOrder = false
): ArrayBuffer {
    if (!DTYPE_MAP.has(data.constructor)) {
        throw new Error('Unsupported TypedArray type for encoding');
    }
    const descr = DTYPE_MAP.get(data.constructor)!;

    // Construct header dict string, note trailing comma required by numpy
    const shapeStr = `(${shape.length === 1 ? shape[0] + ',' : shape.join(', ')})`;
    let header = `{'descr': '${descr}', 'fortran_order': ${fortranOrder ? 'True' : 'False'}, 'shape': ${shapeStr}}`;

    // Encode header as ASCII
    const encoder = new TextEncoder();
    const headerBytes = encoder.encode(header);

    // Calculate padding: header must align to 16 bytes (including magic+version+header_len)
    // Header length field size depends on version (2 bytes for v1, 4 bytes for v2)
    const headerLenSize = version === 1 ? 2 : 4;
    const magicLen = 6; // \x93NUMPY
    const versionLen = 2; // major+minor
    const totalHeaderLen =
        magicLen + versionLen + headerLenSize + headerBytes.length;
    const padLen = (16 - (totalHeaderLen % 16)) % 16;

    // Add padding spaces + newline to header
    const paddedHeader = new Uint8Array(headerBytes.length + padLen + 1);
    paddedHeader.set(headerBytes, 0);
    for (let i = headerBytes.length; i < headerBytes.length + padLen; i++) {
        paddedHeader[i] = 0x20; // space
    }
    paddedHeader[paddedHeader.length - 1] = 0x0a; // newline

    // Final header length
    const finalHeaderLen = paddedHeader.length;

    // Allocate buffer for full npy file
    const buffer = new ArrayBuffer(
        magicLen + versionLen + headerLenSize + finalHeaderLen + data.byteLength
    );
    const view = new DataView(buffer);

    let offset = 0;

    // Write magic string \x93NUMPY
    view.setUint8(offset++, 0x93);
    'NUMPY'.split('').forEach((c) => view.setUint8(offset++, c.charCodeAt(0)));

    // Write version
    view.setUint8(offset++, version);
    view.setUint8(offset++, 0);

    // Write header length
    if (version === 1) {
        view.setUint16(offset, finalHeaderLen, true);
        offset += 2;
    } else {
        view.setUint32(offset, finalHeaderLen, true);
        offset += 4;
    }

    // Write header
    new Uint8Array(buffer, offset, finalHeaderLen).set(paddedHeader);
    offset += finalHeaderLen;

    // Write data bytes
    new Uint8Array(buffer, offset, data.byteLength).set(
        new Uint8Array(data.buffer, data.byteOffset, data.byteLength)
    );

    return buffer;
}
export class NPYArray {
    constructor(
        public readonly data: TypedArray,
        public readonly shape: number[],
        public readonly fortranOrder: boolean
    ) { }
}
// Decode .npy ArrayBuffer into { data: TypedArray, shape: number[], fortranOrder: boolean }
export function decodeNpy(buffer: ArrayBuffer): {
    data: TypedArray;
    shape: number[];
    fortranOrder: boolean;
} {
    const view = new DataView(buffer);

    // Check magic string
    const magic = new Uint8Array(buffer, 0, 6);
    if (magic[0] !== 0x93 || String.fromCharCode(...magic.slice(1)) !== 'NUMPY') {
        throw new Error('Invalid .npy file (missing magic string)');
    }

    // Version
    const major = view.getUint8(6);
    const minor = view.getUint8(7);

    let headerLen: number;
    let offset = 8;

    if (major === 1) {
        headerLen = view.getUint16(offset, true);
        offset += 2;
    } else if (major === 2) {
        headerLen = view.getUint32(offset, true);
        offset += 4;
    } else {
        throw new Error(`Unsupported .npy version ${major}.${minor}`);
    }

    // Read header text
    const headerBytes = new Uint8Array(buffer, offset, headerLen);
    offset += headerLen;

    const decoder = new TextDecoder('ascii');
    const headerText = decoder.decode(headerBytes).trim();

    // Parse header dictionary (Python-like dict literal)
    // Example: {'descr': '<f4', 'fortran_order': False, 'shape': (3, 2), }
    // Use a regex to extract fields
    const descrMatch = headerText.match(/'descr':\s*'([^']+)'/);
    const fortranMatch = headerText.match(/'fortran_order':\s*(True|False)/);
    const shapeMatch = headerText.match(/'shape':\s*\(([^)]*)\)/);

    if (!descrMatch || !fortranMatch || !shapeMatch) {
        throw new Error('Failed to parse .npy header');
    }

    const descr = descrMatch[1];
    const fortranOrder = fortranMatch[1].toLowerCase() === 'true';
    const shapeStr = shapeMatch[1].trim();

    // Parse shape tuple (numbers separated by commas)
    let shape: number[];
    if (shapeStr === '') {
        shape = [];
    } else {
        shape = shapeStr
            .split(',')
            .map((s) => s.trim())
            .filter((s) => s.length > 0)
            .map((s) => parseInt(s, 10));
    }

    // Get TypedArray constructor
    const TypedArrayConstructor = DTYPE_REVERSE_MAP.get(descr);
    if (!TypedArrayConstructor) {
        throw new Error(`Unsupported dtype '${descr}'`);
    }

    // Calculate number of elements
    const size = shape.reduce((a, b) => a * b, 1);

    // Extract data buffer and create typed array view
    const byteOffset = offset;
    const byteLength = size * TypedArrayConstructor.BYTES_PER_ELEMENT;

    if (byteOffset + byteLength > buffer.byteLength) {
        throw new Error('Data buffer is too short');
    }

    const data = new TypedArrayConstructor(buffer, byteOffset, size);

    return new NPYArray(data, shape, fortranOrder);
}
