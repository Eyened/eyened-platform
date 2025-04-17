import { apiUrl } from '$lib/config';
import { importData } from './model';
import type { Task } from './task';

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
    const { count, entities } = await fetchSearchParams('instances', searchParams);
    importData(entities);
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
    const url = new URL(`${apiUrl}/tasks/${task.id}/subtasks`);
    const response = await fetch(url);
    const data = await response.json();
    importData(data);
}
