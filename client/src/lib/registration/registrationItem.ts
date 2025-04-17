import { Matrix } from "$lib/matrix";
import type { Position } from "$lib/types";
import { AffineRegistration } from "./affine";
import { CompositeRegistration } from "./composite";
import { ParabolicRegistration } from "./parabolic";

export interface RegistrationItem {
    source: string;
    target: string;
    mapping: mappingFunction
    glslMapping: string;
    inverse: RegistrationItem;
}

export type mappingFunction = (from: Position) => Position | undefined;

interface RegistrationSet {
    image1: string;
    image2: string;
    transform: Transform;
}
type Transform = CompositeTransform | ProjectiveTransform | ParabolicTransform;
type CompositeTransform = {
    type: 'CompositeTransform';
    transforms: Transform[];
}
type ProjectiveTransform = {
    type: 'ProjectiveTransform';
    Matrix: number[];
}
type ParabolicTransform = {
    type: 'ParabolicTransform';
    dx: number[];
    dy: number[];
}

export function getRegistrationSets(value: RegistrationSet[]) {
    return value.map(loadRegistrationSet);
}

function getTransform(source: string, target: string, item: Transform): RegistrationItem {
    switch (item.type) {
        case 'CompositeTransform':
            const transforms = item.transforms.map(t => getTransform(source, target, t));
            return new CompositeRegistration(source, target, transforms);
        case 'ProjectiveTransform':
            const [a, b, c, d, e, f, g, h, i] = item.Matrix;
            return new AffineRegistration(source, target, new Matrix(a, b, c, d, e, f, g, h, i));
        case 'ParabolicTransform':
            return new ParabolicRegistration(source, target, item.dx, item.dy);
        default:
            throw new Error(`Unknown transform type: ${item.type}`);
    }
}

function loadRegistrationSet(item: RegistrationSet): RegistrationItem {
    const { image1, image2, transform } = item;
    return getTransform(`${image1}`, `${image2}`, transform);
}