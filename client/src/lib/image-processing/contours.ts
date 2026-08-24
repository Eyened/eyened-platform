type segment = [point, point]
type point = [number, number];

export function findContours(img_pixels: Uint8Array, level: number, width: number, height: number, stride: number = 1, offset: number = 0): point[][] {
    const segments = getContourSegments(img_pixels, level, width, height, stride, offset);
    return _assemble_contours(segments);
}

function getContourSegments(img_pixels: Uint8Array, level: number, width: number, height: number, stride: number, offset: number): segment[] {
    const vertex_connect_high = true;
    const get = (x: number, y: number) => {
        const i = x + width * y;
        return img_pixels[stride * i + offset];
    }

    const segments: segment[] = [];
    for (let r0 = 0; r0 < width - 1; r0++) {
        for (let c0 = 0; c0 < height - 1; c0++) {
            const r1 = r0 + 1;
            const c1 = c0 + 1;

            const ul = get(r0, c0);
            const ur = get(r0, c1);
            const ll = get(r1, c0);
            const lr = get(r1, c1);

            let square_case = 0;
            if (ul > level) square_case += 1;
            if (ur > level) square_case += 2;
            if (ll > level) square_case += 4;
            if (lr > level) square_case += 8;

            if (square_case == 0 || square_case == 15) {
                // only do anything if there's a line passing through the
                // square. Cases 0 and 15 are entirely below/above the contour.
                continue;
            }
            const top: point = [r0, c0 + _get_fraction(ul, ur, level)];
            const bottom: point = [r1, c0 + _get_fraction(ll, lr, level)];
            const left: point = [r0 + _get_fraction(ul, ll, level), c0];
            const right: point = [r0 + _get_fraction(ur, lr, level), c1];

            if (square_case == 1)
                segments.push([top, left]);
            else if (square_case == 2)
                segments.push([right, top]);
            else if (square_case == 3)
                segments.push([right, left]);
            else if (square_case == 4)
                segments.push([left, bottom]);
            else if (square_case == 5)
                segments.push([top, bottom]);
            else if (square_case == 6)
                if (vertex_connect_high) {
                    segments.push([left, top]);
                    segments.push([right, bottom]);
                } else {
                    segments.push([right, top]);
                    segments.push([left, bottom]);
                }
            else if (square_case == 7)
                segments.push([right, bottom]);
            else if (square_case == 8)
                segments.push([bottom, right]);
            else if (square_case == 9)
                if (vertex_connect_high) {
                    segments.push([top, right]);
                    segments.push([bottom, left]);
                } else {
                    segments.push([top, left]);
                    segments.push([bottom, right]);
                }
            else if (square_case == 10)
                segments.push([bottom, top]);
            else if (square_case == 11)
                segments.push([bottom, left]);
            else if (square_case == 12)
                segments.push([left, right]);
            else if (square_case == 13)
                segments.push([top, right]);
            else if (square_case == 14)
                segments.push([left, top]);
        }
    }

    return segments;
}

function _get_fraction(from_value: number, to_value: number, level: number) {
    if (to_value == from_value)
        return 0;
    return ((level - from_value) / (to_value - from_value));
}


function _assemble_contours(segments: [point, point][]) {
    const None: undefined = undefined;

    let current_index = 0;
    const contours = new Dict<number, point[]>();
    const starts = new TupleDict<point, [point[], number]>();
    const ends = new TupleDict<point, [point[], number]>();

    for (const [from_point, to_point] of segments) {
        if (from_point === to_point)
            continue;

        const [tail, tail_num] = starts.pop(to_point) ?? [None, None];
        const [head, head_num] = ends.pop(from_point) ?? [None, None];

        if (tail !== None && head !== None) {
            if (tail === head) {
                head.push(to_point);
            } else {
                if (tail_num > head_num) {

                    head.push(...tail);
                    ends.pop(tail[tail.length - 1]);
                    contours.pop(tail_num);

                    const item: [point[], number] = [head, head_num]
                    starts.set(head[0], item);
                    ends.set(head[head.length - 1], item);

                } else {

                    tail.unshift(...head);
                    starts.pop(head[0]);
                    contours.pop(head_num);

                    const item: [point[], number] = [tail, tail_num];
                    starts.set(tail[0], item);
                    ends.set(tail[tail.length - 1], item);
                }
            }
        } else if (tail === None && head === None) {
            const new_contour = [from_point, to_point];
            contours.set(current_index, new_contour);
            starts.set(from_point, [new_contour, current_index]);
            ends.set(to_point, [new_contour, current_index]);
            current_index += 1;
        } else if (head === None) {
            tail!.unshift(from_point);
            starts.set(from_point, [tail!, tail_num!]);
        } else {
            head.push(to_point);
            ends.set(to_point, [head, head_num]);
        }
    }
    const results = Array.from(contours.values());
    return results;
}

class Dict<K, V> {
    private map: Map<K, V>;

    constructor() {
        this.map = new Map<K, V>();
    }

    public has(key: K): boolean {
        return this.map.has(key);
    }

    public set(key: K, value: V): void {
        this.map.set(key, value);
    }

    public get(key: K): V | undefined {
        return this.map.get(key);
    }

    public pop(key: K): V | undefined {
        if (this.map.has(key)) {
            const result = this.map.get(key);
            this.map.delete(key);
            return result;
        }
    }

    public values() {
        return this.map.values();
    }
}

class TupleDict<K extends any[], V> {
    private map: Map<string, V>;

    constructor() {
        this.map = new Map<string, V>();
    }

    private getKeyAsString(key: K): string {
        return key.join(",");
    }

    public has(key: K): boolean {
        const keyString = this.getKeyAsString(key);
        return this.map.has(keyString);
    }

    public set(key: K, value: V): void {
        const keyString = this.getKeyAsString(key);
        this.map.set(keyString, value);
    }

    public get(key: K): V | undefined {
        const keyString = this.getKeyAsString(key);
        return this.map.get(keyString);
    }

    public pop(key: K): V | undefined {
        const keyString = this.getKeyAsString(key);
        if (this.map.has(keyString)) {
            const result = this.map.get(keyString);
            this.map.delete(keyString);
            return result;
        }
    }
}
