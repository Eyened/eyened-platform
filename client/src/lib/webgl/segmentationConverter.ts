import type { SimpleDataRepresentation } from "$lib/datamodel/segmentation.svelte";
import type { DrawingArray } from "./mask.svelte";

export interface ConversionRule {
    from: SimpleDataRepresentation;
    to: SimpleDataRepresentation;
    convert: (data: DrawingArray) => DrawingArray;
}

function binaryToQuestionable(i: number) {
    return i > 0 ? 1 : 0;
}
function binaryToProbability(i: number) {
    return i > 0 ? 255 : 0;
}

function questionableToBinary(i: number) {
    return (i & 1) == 1 ? 1 : 0;
}
function questionableToProbability(i: number) {
    const lookup = [0, 255, 64, 191]; // [00, 01, 10, 11] -> [0, 255, 0.25*255, 0.75*255]
    return lookup[i & 3];
}
function probabilityToBinary(i: number, threshold: number) {
    return i > threshold ? 1 : 0;
}
export const converters = {
    'Binary->DualBitMask': binaryToQuestionable,
    'Binary->Probability': binaryToProbability,
    'DualBitMask->Binary': questionableToBinary,
    'DualBitMask->Probability': questionableToProbability,
    'Probability->Binary': probabilityToBinary,
    'Probability->DualBitMask': probabilityToBinary, // same as binary
}
export function convert(data: DrawingArray, from: SimpleDataRepresentation, to: SimpleDataRepresentation, threshold: number = 127) {
    if (from == to) {
        return data;
    }
    const result = new Uint8Array(data.length);
    const key = `${from}->${to}`;
    if (!(key in converters)) {
        throw new Error(`Conversion from ${from} to ${to} not supported`);
    }
    const func = converters[key as keyof typeof converters];
    for (let i = 0; i < data.length; i++) {
        result[i] = func(data[i], threshold);
    }
    return result;
}