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
