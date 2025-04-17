export class Vec2 {
    constructor(public readonly x: number, public readonly y: number) { }

    length() {
        return Math.sqrt(this.x ** 2 + this.y ** 2);
    }
    dot(other: { x: number, y: number }) {
        return this.x * other.x + this.y * other.y;
    }
    sub(other: { x: number, y: number }) {
        return new Vec2(
            this.x - other.x,
            this.y - other.y
        );
    }
    add(other: { x: number, y: number }) {
        return new Vec2(
            this.x + other.x,
            this.y + other.y
        );
    }
    mul(scalar: number) {
        return new Vec2(
            this.x * scalar,
            this.y * scalar
        );
    }
    cross(other: { x: number, y: number }) {
        return this.x * other.y - this.y * other.x;
    }
    angle() {
        return Math.atan2(this.y, this.x);
    }
}
export function vec2(p: { x: number, y: number }) {
    return new Vec2(p.x, p.y);
}