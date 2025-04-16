import type { Position2D } from './types';
import { multiply, transpose, inv } from 'mathjs';

export class Matrix {
	static identity: Matrix = new Matrix();

	constructor(
		readonly a: number = 1,
		readonly b: number = 0,
		readonly c: number = 0,
		readonly d: number = 0,
		readonly e: number = 1,
		readonly f: number = 0,
		readonly g: number = 0,
		readonly h: number = 0,
		readonly i: number = 1
	) { }

	static from_translate_scale(tx: number, ty: number, sx: number, sy: number): Matrix {
		return new Matrix(
			sx, 0, tx,
			0, sy, ty
		);
	}

	get scale(): number {
		return Math.sqrt(this.a * this.a + this.d * this.d);
	}

	get aspectRatio(): number {
		return this.a / this.e;
	}
	
	get asUniform() {
		return [
			this.a, this.d, this.g,
			this.b, this.e, this.h,
			this.c, this.f, this.i
		];
	}

	apply(point: Position2D) {
		const h = this.g * point.x + this.h * point.y + this.i;
		return {
			x: (this.a * point.x + this.b * point.y + this.c) / h,
			y: (this.d * point.x + this.e * point.y + this.f) / h,
		};
	}

	applyInverse(point: Position2D) {
		return this.inverse.apply(point);
	}

	multiply(matrix: Matrix): Matrix {
		const m1 = this;
		const m2 = matrix;
		return new Matrix(
			m1.a * m2.a + m1.b * m2.d + m1.c * m2.g,
			m1.a * m2.b + m1.b * m2.e + m1.c * m2.h,
			m1.a * m2.c + m1.b * m2.f + m1.c * m2.i,
			m1.d * m2.a + m1.e * m2.d + m1.f * m2.g,
			m1.d * m2.b + m1.e * m2.e + m1.f * m2.h,
			m1.d * m2.c + m1.e * m2.f + m1.f * m2.i,
			m1.g * m2.a + m1.h * m2.d + m1.i * m2.g,
			m1.g * m2.b + m1.h * m2.e + m1.i * m2.h,
			m1.g * m2.c + m1.h * m2.f + m1.i * m2.i
		);
	}

	rotate(angle: number, x: number, y: number): Matrix {
		const translateToOrigin = new Matrix(
			1, 0, -x,
			0, 1, -y);
		const rotate = new Matrix(
			Math.cos(angle), Math.sin(angle), 0,
			-Math.sin(angle), Math.cos(angle), 0);
		const translateBack = new Matrix(
			1, 0, x,
			0, 1, y);
		return translateBack.multiply(rotate).multiply(translateToOrigin).multiply(this);
	}


	zoom(x: number, y: number, factor: number): Matrix {
		const translateToOrigin = new Matrix(
			1, 0, -x,
			0, 1, -y);
		const zoom = new Matrix(
			factor, 0, 0,
			0, factor, 0);
		const translateBack = new Matrix(
			1, 0, x,
			0, 1, y);
		return translateBack.multiply(zoom).multiply(translateToOrigin).multiply(this);
	}

	pan(oldPosition: Position2D, newPosition: Position2D): Matrix {
		const dx = newPosition.x - oldPosition.x;
		const dy = newPosition.y - oldPosition.y;
		return new Matrix(
			this.a, this.b, this.c + dx,
			this.d, this.e, this.f + dy);
	}

	stretch(aspectRatio: number): Matrix {
		// stretch towards aspectRatio		
		return new Matrix(
			this.a, this.b, this.c,
			this.d, aspectRatio * this.a, this.f,
			this.g, this.h, this.i
		);
	}

	get inverse(): Matrix {
		const { a, b, c, d, e, f, g, h, i } = this;

		const denom = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);

		if (denom === 0) {
			throw new Error("Matrix is not invertible");
		}

		return new Matrix(
			(e * i - f * h) / denom,
			(c * h - b * i) / denom,
			(b * f - c * e) / denom,
			(f * g - d * i) / denom,
			(a * i - c * g) / denom,
			(c * d - a * f) / denom,
			(d * h - e * g) / denom,
			(b * g - a * h) / denom,
			(a * e - b * d) / denom
		);
	}
}

export function getMatrixFromPointSets(source: (Position2D | undefined)[], target: (Position2D | undefined)[]): (Matrix | undefined) {
	const n = Math.min(source.length, target.length);

	const A = [];
	const B = [];
	for (let i = 0; i < n; i++) {
		try {
			const { x: x0, y: y0 } = source[i];
			const { x: x1, y: y1 } = target[i];
			A.push([x0, y0, 1, 0, 0, 0]);
			A.push([0, 0, 0, x0, y0, 1]);
			B.push(x1, y1);
		} catch { }

	}
	try {
		const pseudoInverseA = multiply(inv(multiply(transpose(A), A)), transpose(A));
		const [a, b, c, d, e, f] = multiply(pseudoInverseA, B);
		return new Matrix(a, b, c, d, e, f, 0, 0, 1);
	} catch {
		return undefined;
	}
}

