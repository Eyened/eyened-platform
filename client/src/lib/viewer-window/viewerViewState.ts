export type OpenViewerEntry = {
    id: string;
    index?: number;
};

export type ViewerViewStateV2 = {
    version: 2;
    viewers: OpenViewerEntry[];
};

/** Query param for open main viewers (+ optional frame index). */
export const VIEW_STATE_PARAM = "v";

export function storageKey(scope: string): string {
    return `eyened:viewerViewState:${scope}`;
}

/**
 * Parse `v=id.index,id2,id3.5` — `.` separates optional index; `,` separates viewers.
 * Malformed tokens are skipped.
 */
export function parseViewersParam(
    raw: string | null | undefined,
): OpenViewerEntry[] {
    if (!raw) return [];
    const out: OpenViewerEntry[] = [];
    const idOk = /^[A-Za-z0-9_-]+$/;
    for (const part of raw.split(",")) {
        const trimmed = part.trim();
        if (!trimmed) continue;
        const dot = trimmed.lastIndexOf(".");
        if (dot > 0) {
            const id = trimmed.slice(0, dot).trim();
            const indexStr = trimmed.slice(dot + 1).trim();
            if (idOk.test(id) && /^\d+$/.test(indexStr)) {
                const index = Number(indexStr);
                if (Number.isInteger(index) && index >= 0) {
                    out.push({ id, index });
                    continue;
                }
            }
        }
        if (idOk.test(trimmed)) {
            out.push({ id: trimmed });
        }
    }
    return out;
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

export function parseStoredState(
    raw: string | null | undefined,
): ViewerViewStateV2 | null {
    if (!raw) return null;
    try {
        const parsed = JSON.parse(raw) as unknown;
        if (
            !parsed ||
            typeof parsed !== "object" ||
            (parsed as ViewerViewStateV2).version !== 2 ||
            !Array.isArray((parsed as ViewerViewStateV2).viewers)
        ) {
            return null;
        }
        const viewers: OpenViewerEntry[] = [];
        for (const item of (parsed as ViewerViewStateV2).viewers) {
            if (!item || typeof item !== "object") continue;
            const id = (item as OpenViewerEntry).id;
            if (typeof id !== "string" || !id) continue;
            const index = (item as OpenViewerEntry).index;
            if (index === undefined) {
                viewers.push({ id });
            } else if (Number.isInteger(index) && index >= 0) {
                viewers.push({ id, index });
            } else {
                viewers.push({ id });
            }
        }
        return { version: 2, viewers };
    } catch {
        return null;
    }
}

export function serializeStoredState(state: ViewerViewStateV2): string {
    return JSON.stringify(state);
}

/** Map image_id → owning instance id (strip known suffixes like `_proj`). */
export function instanceIdFromImageId(imageId: string): string {
    return imageId.replace(/_proj$/u, "");
}

export type ViewerViewStateController = {
    hydrate(): void;
    enableRecording(): void;
    getViewers(): OpenViewerEntry[];
    peekIndex(imageId: string, depth: number): number | undefined;
    setOpenViewers(viewers: OpenViewerEntry[]): void;
    recordIndex(imageId: string, index: number, depth: number): void;
    prune(instanceIds: readonly string[]): void;
};

export function createViewerViewStateController(options: {
    scope: string;
    getSearchParams: () => URLSearchParams;
    replaceUrl: (params: URLSearchParams) => void;
    storage?: Pick<Storage, "getItem" | "setItem">;
}): ViewerViewStateController {
    const storage = options.storage;
    const key = storageKey(options.scope);
    let viewers: OpenViewerEntry[] = [];
    let recording = false;

    function persist() {
        const params = new URLSearchParams(options.getSearchParams());
        const encoded = serializeViewersParam(viewers);
        if (encoded) params.set(VIEW_STATE_PARAM, encoded);
        else params.delete(VIEW_STATE_PARAM);
        // Drop legacy param if present
        params.delete("frame");
        options.replaceUrl(params);
        if (!storage) return;
        try {
            storage.setItem(
                key,
                serializeStoredState({
                    version: 2,
                    viewers: viewers.map((v) =>
                        v.index === undefined
                            ? { id: v.id }
                            : { id: v.id, index: v.index },
                    ),
                }),
            );
        } catch {
            // private mode / quota — URL sync still applied
        }
    }

    function sameViewers(a: OpenViewerEntry[], b: OpenViewerEntry[]): boolean {
        if (a.length !== b.length) return false;
        return a.every((v, i) => v.id === b[i]?.id && v.index === b[i]?.index);
    }

    return {
        hydrate() {
            recording = false;
            const fromUrl = parseViewersParam(
                options.getSearchParams().get(VIEW_STATE_PARAM),
            );
            if (fromUrl.length > 0) {
                viewers = fromUrl;
                return;
            }
            const stored = parseStoredState(storage?.getItem(key) ?? null);
            viewers = stored?.viewers ?? [];
        },
        enableRecording() {
            recording = true;
            persist();
        },
        getViewers() {
            return viewers.map((v) =>
                v.index === undefined
                    ? { id: v.id }
                    : { id: v.id, index: v.index },
            );
        },
        peekIndex(imageId, depth) {
            const entry = viewers.find((v) => v.id === imageId);
            const index = entry?.index;
            if (
                index === undefined ||
                !Number.isInteger(index) ||
                index < 0 ||
                index >= depth ||
                depth <= 1
            ) {
                return undefined;
            }
            return index;
        },
        setOpenViewers(next) {
            const normalized = next
                .filter((v) => typeof v.id === "string" && v.id.length > 0)
                .map((v) =>
                    v.index !== undefined &&
                    Number.isInteger(v.index) &&
                    v.index >= 0
                        ? { id: v.id, index: v.index }
                        : { id: v.id },
                );
            if (sameViewers(viewers, normalized)) return;
            viewers = normalized;
            if (recording) persist();
        },
        recordIndex(imageId, index, depth) {
            if (!recording || depth <= 1) return;
            if (!Number.isInteger(index) || index < 0 || index >= depth) return;
            const i = viewers.findIndex((v) => v.id === imageId);
            if (i < 0) return;
            if (viewers[i].index === index) return;
            viewers = viewers.map((v, j) =>
                j === i ? { id: v.id, index } : v,
            );
            persist();
        },
        prune(instanceIds) {
            const allowed = new Set(instanceIds);
            const next = viewers.filter((v) =>
                allowed.has(instanceIdFromImageId(v.id)),
            );
            if (sameViewers(viewers, next)) return;
            viewers = next;
            if (recording) persist();
        },
    };
}
