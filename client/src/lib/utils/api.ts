import { apiUrl } from '$lib/config';
import { importData } from '../datamodel/model';
import type { Task } from '../datamodel/task.svelte';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

interface ApiRequestOptions extends RequestInit {
    body?: any;
    json?: boolean;
}

const createRequest = (method: HttpMethod, url: string, options: ApiRequestOptions = {}): RequestInit => {
    const { body, json = true, ...restOptions } = options;
    
    const requestInit: RequestInit = {
        method,
        credentials: 'include',
        ...restOptions,
    };

    if (body) {
        if (json && !(body instanceof FormData)) {
            requestInit.headers = {
                'Content-Type': 'application/json',
                ...restOptions.headers,
            };
            requestInit.body = JSON.stringify(body);
        } else {
            requestInit.body = body;
        }
    }

    return requestInit;
};

export const api = {
    async request(method: HttpMethod, url: string, options: ApiRequestOptions = {}): Promise<Response> {
        return fetch(url, createRequest(method, url, options));
    },

    async get(url: string, options: RequestInit = {}): Promise<Response> {
        return this.request('GET', url, options);
    },

    async post(url: string, body?: any, options: RequestInit = {}): Promise<Response> {
        return this.request('POST', url, { ...options, body });
    },

    async put(url: string, body?: any, options: RequestInit = {}): Promise<Response> {
        return this.request('PUT', url, { ...options, body });
    },

    async patch(url: string, body?: any, options: RequestInit = {}): Promise<Response> {
        return this.request('PATCH', url, { ...options, body });
    },

    async delete(url: string, options: RequestInit = {}): Promise<Response> {
        return this.request('DELETE', url, options);
    },

    // For FormData requests (like file uploads)
    async postForm(url: string, formData: FormData, options: RequestInit = {}): Promise<Response> {
        return this.request('POST', url, { ...options, body: formData, json: false });
    },
};

// Unified data fetching utility
async function fetchFromApi(endpoint: string, searchParams?: URLSearchParams): Promise<any> {
    const url = new URL(`${apiUrl}/${endpoint}`);
    if (searchParams) {
        url.search = searchParams.toString();
    }
    const response = await api.get(url.toString());
    return response.json();
}

// Simplified parameter handling
function createSearchParams(params: Record<string, string | number | Array<string | number>>): URLSearchParams {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (Array.isArray(value)) {
            value.forEach(item => searchParams.append(key, item.toString()));
        } else {
            searchParams.set(key, value.toString());
        }
    }
    return searchParams;
}

// Unified data loading with optional parameter processing
async function loadData(endpoint: string, params?: Record<string, string | number | Array<string | number>>, searchParams?: URLSearchParams) {
    const finalSearchParams = searchParams || (params ? createSearchParams(params) : undefined);
    const data = await fetchFromApi(endpoint, finalSearchParams);
    
    if (data.entities) {
        importData(data.entities);
        return data.next_cursor;
    } else {
        importData(data);
    }
}

// Simplified data loading functions
export async function loadSearchParams(searchParams: URLSearchParams) {
    return loadData('instances', undefined, searchParams);
}

export async function loadParams(params: Record<string, string | number | Array<string | number>>) {
    return loadData('instances', params);
}

export async function loadPatient(PatientIdentifier: string) {
    return loadData('instances', { PatientIdentifier });
}

export async function loadInstances(instanceIDs: number[]) {
    if (instanceIDs.length === 0) return;
    return loadData('instances', { ImageInstanceID: instanceIDs });
}

export async function loadAnnotationInstances(annotationIDs: number[]) {
    if (annotationIDs.length === 0) return;
    return loadData('instances', { AnnotationID: annotationIDs });
}

export async function loadBase() {
    return loadData('data');
}

export async function loadSubtasks(task: Task) {
    return loadData(`tasks/${task.id}/sub-tasks-with-images`);
}