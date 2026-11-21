import { fetchApi } from "$lib/api/client";

export type DataRow = (number | string | null)[];
export type DataSource = Record<string, DataRow[]>;

export class DataSourceError extends Error {
    constructor(
        message: string,
        readonly status: number,
    ) {
        super(message);
    }
}

const cache = new Map<string, Promise<DataSource>>();

export function loadDataSource(
    studyId: number,
    name: string,
): Promise<DataSource> {
    const path = `/studies/${studyId}/data-sources/${encodeURIComponent(name)}`;
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
        // Only successful fetches stay cached, so the next render retries a failure.
        promise.catch(() => cache.delete(path));
        cache.set(path, promise);
    }
    return promise;
}
