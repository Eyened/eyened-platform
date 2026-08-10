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
            (parsed as ViewerViewStateV1).frames === null
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
