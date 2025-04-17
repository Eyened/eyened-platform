import { host } from '$lib/config';
import { writable, type Readable, type Subscriber, type Unsubscriber, type Writable } from 'svelte/store';

export interface ServerPropertyOptions<T> {
    endpoint: string;
    mediaType?: string;
    initialValue?: T;
    autoload?: boolean;
}

export class WriteOnlyServerProperty<T> implements Readable<T | undefined> {
    protected _loaded = false;
    protected val: T | undefined = $state();
    protected trigger: Writable<T | undefined> = writable(undefined);

    protected readonly endpoint: string;
    protected readonly mediaType: string = 'application/json';
    protected readonly autoload: boolean;

    constructor(options: ServerPropertyOptions<T>) {
        const {
            endpoint,
            mediaType = 'application/json',
            initialValue,
            autoload = false
        } = options;

        this.endpoint = endpoint;
        this.mediaType = mediaType;
        this.val = initialValue;
        this.autoload = autoload;
    }

    subscribe(run: Subscriber<T | undefined>, invalidate?: () => void): Unsubscriber {
        return this.trigger.subscribe(run, invalidate);
    }

    get value(): T | undefined {
        return this.val;
    }

    async setValue(value: T) {
        try {
            // Save the value to the server
            const resp = await this.save(value);

            if (resp.status != 204) {
                throw new Error('Failed to save');
            }
            this.val = value;
            this.trigger.update(() => value);

        } catch (e) {
            console.error(e);
            // TODO: Handle error
        }

    }


    private async save(data: T) {
        const url = `${host}/api/${this.endpoint}`
        if (this.mediaType == 'application/json') {
            return putJson(url, data);
        } else if (this.mediaType == 'image/png') {
            return putImage(url, data as HTMLCanvasElement);
        } else if (this.mediaType == 'application/octet-stream') {
            return putOctetStream(url, data);
        }
        console.error('not implemented yet!');
    }
}

export class ServerProperty<T> extends WriteOnlyServerProperty<T> {
    constructor(options: ServerPropertyOptions<T>) {
        super(options);
        if (this.autoload) {
            this.load();
        }
    }
    async load(): Promise<any> {
        // only loads on the first call
        if (this._loaded) {
            return this.val;
        }

        const url = `${host}/api/${this.endpoint}`;

        const fetchFunctions: { [key: string]: () => Promise<any> } = {
            'application/json': () => this.fetchData(url, 'json'),
            'image/png': () => getImage(url),
            'application/octet-stream': () => this.fetchData(url, 'arrayBuffer')
        };

        const fetchData = fetchFunctions[this.mediaType];

        if (!fetchData) {
            console.error('not implemented yet!');
            return;
        }

        try {
            const data = await fetchData();
            this.val = data;
            this.trigger.update(() => data);
            this._loaded = true;

            return data;
        } catch (e) {
            console.warn('Failed to load', e);
        }
    }

    async fetchData(url: string, responseType: 'json' | 'arrayBuffer') {
        const resp = await fetch(url);
        if (resp.status == 404 || resp.status == 204) {
            return undefined;
        } else if (resp.status != 200) {
            throw new Error('Failed to load');
        } else {
            switch (responseType) {
                case 'json':
                    return await resp.json();
                case 'arrayBuffer':
                    return await resp.arrayBuffer();
            }

        }
    }
}

function putJson(url: string, data: any) {
    return fetch(url, {
        method: 'PUT',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json'
        },
        // TODO: config setting to prettify or minify?
        body: JSON.stringify(data, null, '\t')
    });
}

async function putOctetStream(url: string, data: any) {
    return fetch(url, {
        method: 'PUT',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/octet-stream'
        },
        body: data
    });
}

async function putImage(url: string, canvas: HTMLCanvasElement) {
    const blob: Blob = await new Promise((resolve, reject) => {
        canvas.toBlob(blob => {
            if (blob) {
                resolve(blob);
            } else {
                reject(new Error('Blob creation failed'));
            }
        }, 'image/png');
    });

    return fetch(url, {
        method: 'PUT',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'image/png'
        },
        body: blob
    });
}


async function getImage(url: string): Promise<HTMLCanvasElement> {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.crossOrigin = 'Anonymous';
        image.onload = () => resolve(toCanvas(image));
        image.onerror = () => reject(new Error('could not load image'));
        image.src = url;
    });
}

function toCanvas(image: HTMLImageElement | HTMLCanvasElement): HTMLCanvasElement {
    if (!(image instanceof HTMLCanvasElement)) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext("2d")!;
        canvas.width = image.width;
        canvas.height = image.height;
        ctx.drawImage(image, 0, 0);
        return canvas;
    }
    return image;
}