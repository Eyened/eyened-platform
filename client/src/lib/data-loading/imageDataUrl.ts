/** Build `/api/images/{id}/data` with optional query (index, meta, storage_id). */
export function buildImageDataUrl(
    imageId: string,
    query?: Record<string, string | number | boolean | undefined | null>,
): string {
    const url = `/api/images/${imageId}/data`;
    if (!query) {
        return url;
    }
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== null) {
            search.set(key, String(value));
        }
    }
    const qs = search.toString();
    return qs ? `${url}?${qs}` : url;
}

/** Append or replace a query param on a relative or absolute URL (no double `?`). */
export function withQueryParam(
    url: string,
    key: string,
    value: string | number,
): string {
    const hashIndex = url.indexOf("#");
    const withoutHash = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
    const hash = hashIndex >= 0 ? url.slice(hashIndex) : "";
    const qIndex = withoutHash.indexOf("?");
    const path = qIndex >= 0 ? withoutHash.slice(0, qIndex) : withoutHash;
    const search = new URLSearchParams(
        qIndex >= 0 ? withoutHash.slice(qIndex + 1) : "",
    );
    search.set(key, String(value));
    const qs = search.toString();
    return `${path}?${qs}${hash}`;
}
