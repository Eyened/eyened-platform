export type OpenViewerEntry = {
    id: string;
    index?: number;
};

/** Query param for open main viewers (+ optional frame index). */
export const VIEW_STATE_PARAM = "v";

const VIEWER_ID = /^[A-Za-z0-9_-]+$/;

/** Parse one `v=` token, `id` or `id.index`; a malformed token gives null. */
export function parseViewerToken(token: string): OpenViewerEntry | null {
    const trimmed = token.trim();
    if (!trimmed) return null;
    const dot = trimmed.lastIndexOf(".");
    if (dot > 0) {
        const id = trimmed.slice(0, dot).trim();
        const indexStr = trimmed.slice(dot + 1).trim();
        if (VIEWER_ID.test(id) && /^\d+$/.test(indexStr)) {
            return { id, index: Number(indexStr) };
        }
    }
    return VIEWER_ID.test(trimmed) ? { id: trimmed } : null;
}

export function serializeViewersParam(viewers: OpenViewerEntry[]): string {
    return viewers
        .filter((v) => typeof v.id === "string" && v.id.length > 0)
        .map((v) => {
            if (
                v.index !== undefined &&
                Number.isInteger(v.index) &&
                v.index >= 0
            ) {
                return `${v.id}.${v.index}`;
            }
            return v.id;
        })
        .join(",");
}

/** Map image_id → owning instance id (strip known suffixes like `_proj`). */
export function instanceIdFromImageId(imageId: string): string {
    return imageId.replace(/_proj$/u, "");
}
