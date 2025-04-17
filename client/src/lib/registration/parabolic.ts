import type { Position } from "$lib/types";
import type { RegistrationItem } from "./registrationItem";

/**
 * Parabolic registration class
 * Models deformation using a 2nd order polynomial (in 2D)
 * The mapping is defined as:
 * x_out = x - (a00 + a0 + a1*x + a2*y + a3*x^2 + a4*x*y + a5*y^2)
 * y_out = y - (b00 + b0 + b1*x + b2*y + b3*x^2 + b4*x*y + b5*y^2)
 * 
 * The coefficients are stored in dx and dy arrays with a redundant intercept 
 * dx = [a00, a0, a1, a2, a3, a4, a5]
 * dy = [b00, b0, b1, b2, b3, b4, b5]
 */
export class ParabolicRegistration implements RegistrationItem {
    
    constructor(
        public readonly source: string,
        public readonly target: string,
        public readonly dx: number[],
        public readonly dy: number[],
    ) { }

    mapping(p: Position): Position {
        const { x, y } = p;
        // Note: the intercept is added twice
        // this is because the values are exported from python like this: [float(f) for f in [model.intercept_, *model.coef_]
        // perhaps we should export like this: p = list(model_dx.coef_); p[0] += model_dx.intercept_
        const polyFeatures = [1, 1, x, y, x * x, x * y, y * y];
        const dx = dot(this.dx, polyFeatures);
        const dy = dot(this.dy, polyFeatures);
        const x_out = x - dx;
        const y_out = y - dy;
        return { x: x_out, y: y_out, index: 0 };
    }

    get glslMapping(): string {
        return `vec2 mapping(vec2 uv) {
            vec2 coord = uv * u_size_primary.xy;
            float x = coord.x;
            float y = coord.y;
    
            float poly[7];
            poly[0] = 1.0;
            poly[1] = 1.0;
            poly[2] = x;
            poly[3] = y;
            poly[4] = x * x;
            poly[5] = x * y;
            poly[6] = y * y;
    
            float dx_val = 0.0;
            float dy_val = 0.0;
            for (int i = 0; i < 7; i++) {
                dx_val += dx[i] * poly[i];
                dy_val += dy[i] * poly[i];
            }
    
            vec2 result = coord - vec2(dx_val, dy_val);
            return result / u_size_secondary.xy;
        }`;
    }

    get inverse(): ParabolicRegistration {
        const dx_inverse = this.dx.map((val, i) => -val);
        const dy_inverse = this.dy.map((val, i) => -val);
        return new ParabolicRegistration(this.target, this.source, dx_inverse, dy_inverse);
    }
}


function dot(a: number[], b: number[]): number {
    return a.reduce((sum, ai, i) => sum + ai * b[i], 0);
}