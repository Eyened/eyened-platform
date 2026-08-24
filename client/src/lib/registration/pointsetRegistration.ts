import { Matrix, getMatrixFromPointSets } from "$lib/matrix";
import type { Position2D } from "$lib/types";
import { AffineRegistration } from "./affine";


export function getPointsetRegistrations(data: { [img_id: string]: (Position2D | undefined)[] }): AffineRegistration[] {
    const result: AffineRegistration[] = [];
    const keys = Object.keys(data).sort();
    
    for (let i = 0; i < keys.length; i++) {
        const source = keys[i];
        const sourcePoints = data[source];
        
        for (let j = i + 1; j < keys.length; j++) {
            const target = keys[j];
            const targetPoints = data[target];
            
            const M = getMatrixFromPointSets(sourcePoints, targetPoints);
            if (M) {
                result.push(new AffineRegistration(source, target, M));
            }
        }
    }
    return result;
}

export interface AffineItem {
    image0: number,
    image1: number,
    transform: [number, number, number, number, number, number]
}
function getAffineItem(data: AffineItem) {
    const source = `${data.image0}`;
    const target = `${data.image1}`;
    const [a, b, c, d, e, f] = data.transform;
    // the order of elements in the matrix is different 
    const M = new Matrix(a, c, e, b, d, f);
    return new AffineRegistration(source, target, M)
}

export function getAffineTransforms(data: AffineItem[]): AffineRegistration[] {
    return data.map(getAffineItem);
}
