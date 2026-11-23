export type SetControl = "prev" | "next" | "primary";

/** What one set leaves the next: the viewports by position and the control that moved. */
export interface SetHandoff {
    selected: number;
    maximised: number | null;
    control: SetControl;
}

const KEY = "eyened.setHandoff";

export function writeHandoff(note: SetHandoff): void {
    try {
        sessionStorage.setItem(KEY, JSON.stringify(note));
    } catch {
        // Without storage the next set opens as it would from a link.
    }
}

let taken: SetHandoff | null | undefined;

/** The last set's note, read once per page and deleted, so a reload opens as usual. */
export function takeHandoff(): SetHandoff | null {
    if (taken !== undefined) return taken;
    try {
        const raw = sessionStorage.getItem(KEY);
        sessionStorage.removeItem(KEY);
        taken = raw ? (JSON.parse(raw) as SetHandoff) : null;
    } catch {
        taken = null;
    }
    return taken;
}
