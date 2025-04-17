export function deepEquals(a: any, b: any): boolean {
    if (a === b) return true;

    if (a === null || b === null ||
        typeof a !== 'object' || typeof b !== 'object') {
        return a === b;
    }

    if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) return false;
        return a.every((val, i) => deepEquals(val, b[i]));
    }

    const keysA = Object.keys(a);
    const keysB = Object.keys(b);

    if (keysA.length !== keysB.length) return false;

    return keysA.every(key => keysB.includes(key) && deepEquals(a[key], b[key]));
}

export function deepcopy<T>(obj: T): T {
    if (obj === null || typeof obj !== 'object') {
        return obj;
    }

    if (Array.isArray(obj)) {
        return obj.map(item => deepcopy(item)) as unknown as T;
    }

    if (obj instanceof Map) {
        const copy = new Map();
        obj.forEach((value, key) => {
            copy.set(key, deepcopy(value));
        });
        return copy as unknown as T;
    }

    if (obj instanceof Set) {
        const copy = new Set();
        obj.forEach(value => {
            copy.add(deepcopy(value));
        });
        return copy as unknown as T;
    }

    if (obj instanceof Date) {
        return new Date(obj.getTime()) as unknown as T;
    }

    if (obj instanceof RegExp) {
        return new RegExp(obj) as unknown as T;
    }

    const copy = {} as T;
    for (const key in obj) {
        if (Object.prototype.hasOwnProperty.call(obj, key)) {
            copy[key as keyof T] = deepcopy(obj[key]);
        }
    }
    return copy;
}