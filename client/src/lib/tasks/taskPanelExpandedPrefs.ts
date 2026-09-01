export const TASK_PANEL_EXPANDED_STORAGE_KEY = "eyened:taskPanelExpanded";

type ExpandedMap = Record<string, boolean>;

function canUseStorage(): boolean {
    try {
        return typeof localStorage !== "undefined";
    } catch {
        return false;
    }
}

function readAll(): ExpandedMap {
    if (!canUseStorage()) return {};
    try {
        const raw = localStorage.getItem(TASK_PANEL_EXPANDED_STORAGE_KEY);
        if (!raw) return {};
        const parsed: unknown = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            return {};
        }
        return parsed as ExpandedMap;
    } catch {
        return {};
    }
}

export function getTaskPanelExpanded(
    taskId: number,
    defaultValue: boolean,
): boolean {
    const value = readAll()[String(taskId)];
    return typeof value === "boolean" ? value : defaultValue;
}

export function setTaskPanelExpanded(taskId: number, expanded: boolean): void {
    if (!canUseStorage()) return;
    try {
        const all = readAll();
        all[String(taskId)] = expanded;
        localStorage.setItem(
            TASK_PANEL_EXPANDED_STORAGE_KEY,
            JSON.stringify(all),
        );
    } catch {
        // fail soft: in-memory toggle still works for this page load
    }
}
