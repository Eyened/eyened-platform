import { fetchApi } from "$lib/api/client";
import type { DataSourceGET } from "../../types/openapi_types";

export type DataRow = (number | string | null)[];

export type TablesContribution = {
    kind: "tables";
    groups: Record<string, DataRow[]>;
};

const cache = new Map<string, Promise<unknown>>();

function cachedJson<T>(path: string): Promise<T> {
    if (!cache.has(path)) {
        const promise = fetchApi(path).then((response) => {
            if (!response.ok) {
                throw new Error(`Failed to load ${path}`);
            }
            return response.json();
        });
        cache.set(path, promise);
    }
    return cache.get(path) as Promise<T>;
}

export function listDataSources(studyId: number): Promise<DataSourceGET[]> {
    return cachedJson(`/studies/${studyId}/data-sources`);
}

export function loadDataSource(
    studyId: number,
    name: string,
): Promise<unknown> {
    return cachedJson(
        `/studies/${studyId}/data-sources/${encodeURIComponent(name)}`,
    );
}

export function isTablesContribution(
    data: unknown,
): data is TablesContribution {
    if (typeof data !== "object" || data === null) return false;
    const record = data as { kind?: unknown; groups?: unknown };
    return record.kind === "tables" && typeof record.groups === "object";
}
