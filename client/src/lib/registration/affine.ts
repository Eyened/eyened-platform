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
        public readonly M: Matrix,
    ) {}

    mapping(p: Position): Position {
        return { ...this.M.apply(p), index: 0 };
    }

    get glslMapping(): string {
        return `vec2 map_hop(vec2 uv) {
            mat3 transform = ${mat3(this.M)}
            vec3 transformedUV = transform * vec3(uv * u_size_primary.xy, 1.0);
            vec2 result = transformedUV.xy / transformedUV.z;
            return result / u_size_secondary.xy;
        }`;
    }

    get inverse(): AffineRegistration {
        const inverseMatrix = this.M.inverse;
        return new AffineRegistration(this.target, this.source, inverseMatrix);
    }
}

/**
 * GLSL `mat3(...)` takes its arguments column by column, so the emitted order is
 * the same column-major order as `Matrix.asUniform`. Deriving it from that getter
 * keeps the shader path and the `uniformMatrix3fv` path from drifting apart.
 */
export function mat3(M: Matrix): string {
    const [c0x, c0y, c0z, c1x, c1y, c1z, c2x, c2y, c2z] = M.asUniform;
    return `mat3(
        ${f(c0x)}, ${f(c0y)}, ${f(c0z)},
        ${f(c1x)}, ${f(c1y)}, ${f(c1z)},
        ${f(c2x)}, ${f(c2y)}, ${f(c2z)}
    );`;
}

export function f(value: number): string {
    // return glsl code for a float value
    return Number.isInteger(value) ? value.toFixed(1) : value.toString();
}
