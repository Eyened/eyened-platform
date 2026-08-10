export type ViewerViewStateV1 = {
    version: 1;
    frames: Record<string, number>;
};

export function storageKey(scope: string): string {
    return `eyened:viewerViewState:${scope}`;
}

export function parseFrameParam(
    raw: string | null | undefined,
): Record<string, number> {
    if (!raw) return {};
    const out: Record<string, number> = {};
    for (const part of raw.split(",")) {
        const trimmed = part.trim();
        if (!trimmed) continue;
        const colon = trimmed.indexOf(":");
        if (colon <= 0) continue;
        const id = trimmed.slice(0, colon).trim();
        const indexStr = trimmed.slice(colon + 1).trim();
        if (!id || !/^\d+$/.test(indexStr)) continue;
        const index = Number(indexStr);
        if (!Number.isInteger(index) || index < 0) continue;
        out[id] = index;
    }
    return out;
}

export function serializeFrameParam(frames: Record<string, number>): string {
    return Object.entries(frames)
        .filter(
            ([, index]) =>
                Number.isInteger(index) && index >= 0 && Number.isFinite(index),
        )
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([id, index]) => `${id}:${index}`)
        .join(",");
}

export function parseStoredState(
    raw: string | null | undefined,
): ViewerViewStateV1 | null {
    if (!raw) return null;
    try {
        const parsed = JSON.parse(raw) as unknown;
        if (
            !parsed ||
            typeof parsed !== "object" ||
            (parsed as ViewerViewStateV1).version !== 1 ||
            typeof (parsed as ViewerViewStateV1).frames !== "object" ||
            (parsed as ViewerViewStateV1).frames === null ||
            Array.isArray((parsed as ViewerViewStateV1).frames)
        ) {
            return null;
        }
        const frames: Record<string, number> = {};
        for (const [id, index] of Object.entries(
            (parsed as ViewerViewStateV1).frames,
        )) {
            if (Number.isInteger(index) && (index as number) >= 0) {
                frames[id] = index as number;
            }
        }
        return { version: 1, frames };
    } catch {
        return null;
    }
}

export function serializeStoredState(state: ViewerViewStateV1): string {
    return JSON.stringify(state);
}

export type ViewerViewStateController = {
    hydrate(): void;
    enableRecording(): void;
    peekFrame(instanceId: string, depth: number): number | undefined;
    record(instanceId: string, index: number, depth: number): void;
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
    let frames: Record<string, number> = {};
    let recording = false;

    function persist() {
        const params = new URLSearchParams(options.getSearchParams());
        const encoded = serializeFrameParam(frames);
        if (encoded) params.set("frame", encoded);
        else params.delete("frame");
        options.replaceUrl(params);
        if (!storage) return;
        try {
            storage.setItem(
                key,
                serializeStoredState({ version: 1, frames: { ...frames } }),
            );
        } catch {
            // private mode / quota — URL sync still applied
        }
    }

    return {
        hydrate() {
            recording = false;
            const fromUrl = parseFrameParam(
                options.getSearchParams().get("frame"),
            );
            if (Object.keys(fromUrl).length > 0) {
                frames = fromUrl;
                return;
            }
            const stored = parseStoredState(storage?.getItem(key) ?? null);
            frames = stored?.frames ?? {};
        },
        enableRecording() {
            recording = true;
            persist();
        },
        peekFrame(instanceId, depth) {
            const index = frames[instanceId];
            if (
                !Number.isInteger(index) ||
                index < 0 ||
                index >= depth ||
                depth <= 1
            ) {
                return undefined;
            }
            return index;
        },
        record(instanceId, index, depth) {
            if (!recording || depth <= 1) return;
            if (!Number.isInteger(index) || index < 0 || index >= depth) return;
            if (frames[instanceId] === index) return;
            frames[instanceId] = index;
            persist();
        },
        prune(instanceIds) {
            const allowed = new Set(instanceIds);
            let changed = false;
            for (const id of Object.keys(frames)) {
                if (!allowed.has(id)) {
                    delete frames[id];
                    changed = true;
                }
            }
            if (changed && recording) persist();
        },
    };
}
