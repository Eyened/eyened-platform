import { fetchApi } from "$lib/api/client";
import type { DataSourceGET } from "../../types/openapi_types";

export type DataRow = (number | string | null)[];

export type TablesContribution = {
    kind: "tables";
    groups: Record<string, DataRow[]>;
};

export class DataSourceError extends Error {
    constructor(
        message: string,
        readonly status: number,
    ) {
        super(message);
        this.name = "DataSourceError";
    }
}

const cache = new Map<string, Promise<unknown>>();

function cachedJson<T>(path: string): Promise<T> {
    let promise = cache.get(path);
    if (!promise) {
        promise = fetchApi(path).then((response) => {
            if (!response.ok) {
                throw new DataSourceError(
                    `Failed to load ${path}`,
                    response.status,
                );
            }
            return response.json();
        });
        // Only a successful fetch stays cached, so the next render retries a failure.
        promise.catch(() => {
            if (cache.get(path) === promise) cache.delete(path);
        });
        cache.set(path, promise);
    }
    return promise as Promise<T>;
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
    if (typeof data !== "object" || data === null || Array.isArray(data)) {
        return false;
    }
    const record = data as { kind?: unknown; groups?: unknown };
    const groups = record.groups;
    return (
        record.kind === "tables" &&
        typeof groups === "object" &&
        groups !== null &&
        !Array.isArray(groups)
    );
}
