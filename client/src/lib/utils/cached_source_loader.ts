export type DataRow = (number | string | null)[];
export type DataItem = { tag: string, values: DataRow[] };
export type DataSource = { [tag: string]: DataItem[] };

const cache = new Map<string, Promise<DataSource>>();

export function loadDataSource(url: string, cached: boolean = true): Promise<DataSource> {
    if (cached && cache.has(url)) {
        return cache.get(url)!;
    }
    const promise = fetch(url).then((response) => response.json());
    if (cached) {
        cache.set(url, promise);
    }
    return promise;
}

/**
 * Resolves a template URL with the given context.
 * 
 * @param template url with placeholders e.g. ${patient.identifier} or ${patient.identifier:defaultValue}
 * @param context object with the data to be substituted
 * @returns the resolved URL
 */
export function resolveURL(template: string, context: any): string {
    return template.replace(/\$\{([^}:]+(?:\.[^}:]+)*)(?::([^}]*))?\}/g, (_, key, defaultValue) => {
        try {
            const value = resolveValue(key, context);
            if (value instanceof Date) {
                return value.getFullYear() + "-" + (value.getMonth() + 1) + "-" + value.getDate();
            }
            return String(value);
        } catch (error) {
            console.error(`Failed to resolve ${key}:`, error);
            return defaultValue ?? "";
        }
    });
}
export function resolveValue(key: string, context: any): any {
    const path = key.split(".");
    let value = context;
    for (const p of path) {
        if (value == null || !(p in value)) {
            return null;
        }
        value = value[p];
    }
    return value;
}