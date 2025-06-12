import { apiUrl } from '$lib/config';
import { decodeNpy } from '$lib/utils/npy_loader';
import { writable, type Readable, type Subscriber, type Unsubscriber, type Updater, type Writable } from 'svelte/store';


export class ServerBackedFKMapping<T> implements Writable<T | undefined> {

    private _value: Writable<T | undefined> = writable(undefined);

    constructor(private readonly collectionName: string, private readonly key: string) {

    }

    private async setServerValue(value: T | undefined) {
        const url = `${apiUrl}/${this.collectionName}/${value?.id}`;
        const resp = await fetch(url);
        if (resp.status === 404 || resp.status === 204) {
            return undefined;
        } else if (resp.status !== 200) {
            throw new Error(`Failed to load: ${resp.status} ${resp.statusText}`);
        }
    }

    update(updater: Updater<T | undefined>): void {
        this._value.update(updater);
    }

    set(value: T | undefined): void {
        this._value.set(value);
    }

    subscribe(run: Subscriber<T | undefined>, invalidate?: () => void): Unsubscriber {
        return this._value.subscribe(run, invalidate);
    }



}



export interface ServerPropertyOptions<T> {
    endpoint: string;
    initialValue?: T;
    autoload?: boolean;
}

export class WriteOnlyServerProperty<T> implements Readable<T | undefined> {
    protected _loaded = false;
    protected val: T | undefined = $state();
    protected trigger: Writable<T | undefined> = writable(undefined);

    protected readonly endpoint: string;
    protected readonly autoload: boolean;

    constructor(options: ServerPropertyOptions<T>) {
        const {
            endpoint,
            initialValue,
            autoload = false
        } = options;

        this.endpoint = endpoint;
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
        const url = `${apiUrl}/${this.endpoint}`
        if (data instanceof HTMLCanvasElement) {
            return putImage(url, data as HTMLCanvasElement);
        } else if (data instanceof ArrayBuffer || data instanceof Blob) {
            return putOctetStream(url, data);
        }
        return putJson(url, data);

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
        const url = `${apiUrl}/${this.endpoint}`;


        try {
            const data = await this.fetchData(url);
            this.val = data;
            this.trigger.update(() => data);
            this._loaded = true;

            return data;
        } catch (e) {
            console.warn('Failed to load', e);
        }
    }

    async fetchData(url: string) {
        const resp = await fetch(url);
        if (resp.status === 404 || resp.status === 204) {
            return undefined;
        } else if (resp.status !== 200) {
            throw new Error(`Failed to load: ${resp.status} ${resp.statusText}`);
        }

        const responseType = resp.headers.get('Content-Type');
        if (!responseType) {
            throw new Error('No Content-Type header in response');
        }

        if (responseType.includes('application/json')) {
            const value = await resp.json();
            console.log('loaded', value);
            return value;
        } else if (responseType.includes('application/octet-stream')) {
            const arrayBuffer = await resp.arrayBuffer();

            const bytes = new Uint8Array(arrayBuffer);

            // Check for the magic string "\x93NUMPY"
            const magic = [0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59]; // \x93NUMPY
            const isNpy = magic.every((byte, i) => bytes[i] === byte);
            if (isNpy) {
                return decodeNpy(arrayBuffer);
            }
            return arrayBuffer;
        } else if (responseType.includes('image/png')) {
            const blob = await resp.blob();
            return await createImageBitmap(blob);
        } else {
            throw new Error(`Unsupported media type: ${responseType}`);
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

async function putOctetStream(url: string, data: ArrayBuffer | Blob) {
    // Convert ArrayBuffer to Blob if needed
    const blob = data instanceof ArrayBuffer ? new Blob([data]) : data;

    // Compress the data using CompressionStream
    const compressedBlob = await blob.arrayBuffer().then(buffer => {
        return new Response(new Blob([buffer]).stream().pipeThrough(new CompressionStream('gzip')));
    }).then(response => response.blob());

    return fetch(url, {
        method: 'PUT',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/octet-stream',
            'Content-Encoding': 'gzip'
        },
        body: compressedBlob
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