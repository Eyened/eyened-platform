import { apiUrl } from '$lib/config';
import { authClient, type UserResponse } from '../../auth';
import { importData } from '../datamodel/model';
import type { Task } from '../datamodel/task.svelte';


type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
type DataType = 'json' | 'binary' | 'form';

// Token refresh state
let isRefreshing = false;
let refreshPromise: Promise<UserResponse> | null = null;

const createRequest = (method: HttpMethod, body: any, dataType: DataType): RequestInit => {
    const requestInit: RequestInit = {
        method,
        credentials: 'include',
    };

    if (body) {
        switch (dataType) {
            case 'json':
                requestInit.headers = {
                    'Content-Type': 'application/json',
                };
                requestInit.body = JSON.stringify(body);
                break;

            case 'binary':
                requestInit.headers = {
                    'Content-Type': 'application/octet-stream',
                };
                requestInit.body = body;
                break;

            case 'form':
                requestInit.body = body;
                break;
        }
    }

    return requestInit;
};

// Handle token refresh with deduplication
async function handleTokenRefresh(): Promise<UserResponse> {
    console.log('handleTokenRefresh');
    if (isRefreshing) {
        // If already refreshing, wait for the existing promise
        return refreshPromise!;
    }

    isRefreshing = true;
    refreshPromise = authClient.refresh();
    
    try {
        const result = await refreshPromise;
        return result;
    } finally {
        isRefreshing = false;
        refreshPromise = null;
    }
}

export const api = {
    async request(method: HttpMethod, base_url: string, body: any, dataType: DataType): Promise<Response> {
        const url = `${apiUrl}/${base_url}`;
        const makeRequest = async (): Promise<Response> => {
            return fetch(url, createRequest(method, body, dataType));
        };

        // First attempt
        let response = await makeRequest();

        // If we get 401, try to refresh token and retry once
        if (response.status === 401) {
            try {
                await handleTokenRefresh();
                // Retry the original request with the new token
                response = await makeRequest();
            } catch (error) {
                // If refresh fails, redirect to login
                window.location.href = '/login';
                throw error;
            }
        }

        return response;
    },

    async get(url: string): Promise<Response> {
        return this.request('GET', url, null, 'json');
    },

    async post(url: string, body?: any, dataType: DataType = 'json'): Promise<Response> {
        return this.request('POST', url, body, dataType);
    },

    async put(url: string, body?: any, dataType: DataType = 'json'): Promise<Response> {
        return this.request('PUT', url, body, dataType);
    },

    async patch(url: string, body?: any, dataType: DataType = 'json'): Promise<Response> {
        return this.request('PATCH', url, body, dataType);
    },

    async delete(url: string): Promise<Response> {
        return this.request('DELETE', url, null, 'json');
    }
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