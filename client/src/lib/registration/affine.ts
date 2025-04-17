import type { Position } from "$lib/types";
import { Matrix } from "$lib/matrix";
import type { RegistrationItem } from "./registrationItem";

/**
 * AffineRegistration class represents a registration between two images using a 3x3 transformation matrix.
 * So more general transformations (projective) could also be applied (perhaps the class should be renamed).
 */
export class AffineRegistration implements RegistrationItem {

    constructor(
        public readonly source: string,
        public readonly target: string,
        public readonly M: Matrix) { }

    mapping(p: Position): Position {
        return { ...this.M.apply(p), index: 0 };
    }

    get glslMapping(): string {
        return `vec2 mapping(vec2 uv) {
            mat3 transform = ${mat3(this.M)}
            vec3 transformedUV = transform * vec3(uv * u_size_primary.xy, 1.0);
            vec2 result = transformedUV.xy / transformedUV.z;
            return result / u_size_secondary.xy;
        }`;
    }

    get inverse(): AffineRegistration {
        const inverseMatrix = this.M.inverse
        return new AffineRegistration(this.target, this.source, inverseMatrix);
    }
}


export function mat3(M: Matrix): string {
    return `mat3(
        ${f(M.d)}, ${f(M.e)}, ${f(M.f)},
        ${f(M.a)}, ${f(M.b)}, ${f(M.c)},
        ${f(M.g)}, ${f(M.h)}, ${f(M.i)}
    );`;
}

export function f(value: number): string {
    // return glsl code for a float value
    return Number.isInteger(value) ? value.toFixed(1) : value.toString();
}