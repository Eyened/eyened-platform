import { thumbnailHost } from '$lib/config.js';
// import type { Instance } from '$lib/datamodel/instance.svelte';
import type { components } from '../../types/openapi';
type Instance = components['schemas']['InstanceGET'];

export class DefaultDict<T, Q> extends Map<T, Q> {
    defaultFactory: () => Q;
    constructor(defaultFactory: () => Q) {
        super();
        this.defaultFactory = defaultFactory;
    }
    get(name: T): Q {
        if (this.has(name)) {
            return super.get(name)!;
        } else {
            const value = this.defaultFactory();
            this.set(name, value);
            return value;
        }
    }
}

export function parseDate(dateString: string): Date | undefined {
    try {
        const [year, month, day, hour, minute, second] = dateString.split(/[- :]/).map(Number);
        return new Date(year, month - 1, day, hour, minute, second);
    } catch (error) {
    }
}

export function getThumbUrl(Instance: Instance) {
    if (!Instance.thumbnail_path) return;

    let image_url = [thumbnailHost, Instance.thumbnail_path].join('/') + '_144.jpg';

    return encodeURI(image_url);
}

export function arraysEqual(a: any[], b: any[]): boolean {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return false;
    }
    return true;
}