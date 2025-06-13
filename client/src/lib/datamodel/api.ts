import { apiUrl } from '$lib/config';
import { decodeNpy } from '$lib/utils/npy_loader';
import { data, importData } from './model';
import type { Task } from './task.svelte';

export class DataEndpoint<T> {
    protected _loaded = false;
    protected val: T | undefined = $state(undefined);

    constructor(private readonly endpoint: string) {

    }

    async load(): Promise<T> {
        // only loads on the first call
        if (this._loaded) {
            return this.val!;
        }
        const url = `${apiUrl}/${this.endpoint}`;
        this.val = await load(url);
        this._loaded = true;
        return this.val!;
    }

    async update(data: T) {
        console.log('update', data);
    }
}


function generateUrlSearchParams(params: Record<string, string | number | Array<string | number>>): URLSearchParams {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (Array.isArray(value)) {
            for (const item of value) {
                searchParams.append(key, item.toString());
            }
        } else {
            searchParams.set(key, value.toString());
        }
    }
    return searchParams;
}

function fetchData(endpoint: string, params: Record<string, string | number | Array<string | number>> = {}): Promise<any> {
    const searchParams = generateUrlSearchParams(params)
    return fetchSearchParams(endpoint, searchParams);
}

async function fetchSearchParams(endpoint: string, searchParams: URLSearchParams): Promise<any> {
    const url = new URL(`${apiUrl}/${endpoint}`);
    url.search = searchParams.toString();
    const response = await fetch(url.toString());
    return response.json();
}

export async function loadSearchParams(searchParams: URLSearchParams) {
    const resp = await fetchSearchParams('instances', searchParams);
    const { next_cursor, entities } = resp;
    importData(entities);
    return next_cursor;
}

export async function loadParams(params: Record<string, string | number | Array<string | number>>) {
    const { count, entities } = await fetchData('instances', params);
    importData(entities);
}
export async function loadPatient(PatientIdentifier: string) {
    await loadParams({ PatientIdentifier });
}

export async function loadInstances(instanceIDs: number[]) {
    if (instanceIDs.length === 0) return;
    await loadParams({ ImageInstanceID: instanceIDs });
}

export async function loadAnnotationInstances(annotationIDs: number[]) {
    if (annotationIDs.length === 0) return;
    await loadParams({ AnnotationID: annotationIDs });
}

export async function loadBase() {
    const baseData = await fetchData('data');
    importData(baseData);
}

export async function loadSubtasks(task: Task) {
    const url = new URL(`${apiUrl}/tasks/${task.id}/subtasks-with-images`);
    const response = await fetch(url);
    const data = await response.json();
    importData(data);
}


async function load(url: string) {
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