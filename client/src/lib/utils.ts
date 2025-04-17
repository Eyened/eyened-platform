export function groupBy(xs: { [key: string | number]: any }[], key: string | number) {
    return xs.reduce(function (rv, x) {
        (rv[x[key]] = rv[x[key]] || []).push(x);
        return rv;
    }, {});
}
export function groupByFunction<K, V>(xs: V[], key: (arg0: V) => K): Map<K, V[]> {
    return xs.reduce(function (map, x) {
        const k = key(x);
        if (map.has(k)) {
            map.get(k).push(x);
        } else {
            map.set(k, [x]);
        }
        return map;
    }, new Map());
}

export class DefaultDictList<K, V> extends Map<K, V[]> {
    get(key: K): V[] {
        if (!this.has(key)) {
            this.set(key, []);
        }
        return super.get(key)!;
    }
}

export function splitTail(str: string, sep: string) {
    const index = str.lastIndexOf(sep);
    return [str.substring(0, index), str.substring(index + 1)];
}



export type Color = [number, number, number];

export function toHex(color: Color) {
    const [r, g, b] = color;
    return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
}

export function fromHex(hex: string): [number, number, number] {
    const bigint = parseInt(hex.slice(1), 16);
    return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
}


export function get_url_params() {
    const urlSearchParams = new URLSearchParams(window.location.search);
    return Object.fromEntries(urlSearchParams.entries());
}

export class Deferred<T> {
    promise: Promise<T>;
    resolve!: (value: T | PromiseLike<T>) => void;
    reject!: (reason?: any) => void;

    constructor() {
        this.promise = new Promise<T>((res, rej) => {
            this.resolve = res;
            this.reject = rej;
        });
    }
}
