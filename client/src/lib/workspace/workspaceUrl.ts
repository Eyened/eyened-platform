import {
    parseViewerToken,
    serializeViewersParam,
    VIEW_STATE_PARAM,
    type OpenViewerEntry,
} from "$lib/viewer-window/viewerViewState";
import { getPreset } from "./presets";
import { ARRANGE_ORDERS, type ArrangeOrder } from "./workspaceRules";

/** What one slot shows; null is an empty slot. */
export type SlotEntry = OpenViewerEntry | null;

export interface WorkspaceUrlState {
    /** By slot position; an empty entry is an empty slot. */
    v: SlotEntry[];
    layout: string | null;
    page: number;
    arrange: ArrangeOrder;
}

const LAYOUT = "layout";
const PAGE = "page";
const ARRANGE = "arrange";
/** On /view and in a task alike; a missing or unknown `arrange=` means it. */
// ASSUMPTION: the URL leaves out `arrange=` when it is the default (plan decision 18).
const DEFAULT_ARRANGE: ArrangeOrder = "opened";

export function parseWorkspaceParams(
    params: URLSearchParams,
): WorkspaceUrlState {
    const raw = params.get(VIEW_STATE_PARAM);
    const layout = params.get(LAYOUT);
    const page = Number(params.get(PAGE));
    const arrange = params.get(ARRANGE);
    return {
        v: raw ? raw.split(",").map(parseViewerToken) : [],
        layout: layout && getPreset(layout) ? layout : null,
        page: Number.isInteger(page) && page >= 1 ? page : 1,
        arrange:
            ARRANGE_ORDERS.find((order) => order === arrange) ??
            DEFAULT_ARRANGE,
    };
}

/** Returns a copy of `base` with the workspace params set; other params, like `instances=`, are kept. */
export function writeWorkspaceParams(
    base: URLSearchParams,
    state: WorkspaceUrlState,
): URLSearchParams {
    const params = new URLSearchParams(base);
    const setOrDelete = (key: string, value: string | null) => {
        if (value === null) params.delete(key);
        else params.set(key, value);
    };
    setOrDelete(
        VIEW_STATE_PARAM,
        state.v.some((entry) => entry !== null)
            ? state.v
                  .map((entry) => (entry ? serializeViewersParam([entry]) : ""))
                  .join(",")
            : null,
    );
    setOrDelete(LAYOUT, state.layout);
    setOrDelete(PAGE, state.page > 1 ? String(state.page) : null);
    setOrDelete(
        ARRANGE,
        state.arrange === DEFAULT_ARRANGE ? null : state.arrange,
    );
    return params;
}

/** Debounced writer: only the latest state reaches the URL (browsers rate-limit history updates). */
export function createWorkspaceUrlWriter(options: {
    getSearchParams: () => URLSearchParams;
    replaceUrl: (params: URLSearchParams) => void;
    delayMs?: number;
}): { write(state: WorkspaceUrlState): void; flush(): void } {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let pending: WorkspaceUrlState | null = null;

    function flush() {
        if (timer !== undefined) clearTimeout(timer);
        timer = undefined;
        if (!pending) return;
        const state = pending;
        pending = null;
        try {
            options.replaceUrl(
                writeWorkspaceParams(options.getSearchParams(), state),
            );
        } catch {
            // Browser history rate limits.
        }
    }

    return {
        write(state) {
            pending = state;
            if (timer !== undefined) clearTimeout(timer);
            timer = setTimeout(flush, options.delayMs ?? 250);
        },
        flush,
    };
}
