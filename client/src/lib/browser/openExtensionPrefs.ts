export const OPEN_EXTENSIONS_STORAGE_KEY = "eyened.study-extensions.open";

function canUseStorage(): boolean {
    try {
        return typeof localStorage !== "undefined";
    } catch {
        return false;
    }
}

export function readOpenExtensionNames(allNames: string[]): string[] {
    if (!canUseStorage()) return allNames;
    try {
        const raw = localStorage.getItem(OPEN_EXTENSIONS_STORAGE_KEY);
        if (raw === null) return allNames;
        const parsed: unknown = JSON.parse(raw);
        if (
            !Array.isArray(parsed) ||
            parsed.some((name) => typeof name !== "string")
        ) {
            return allNames;
        }
        const allowed = new Set(allNames);
        return parsed.filter((name) => allowed.has(name));
    } catch {
        return allNames;
    }
}

export function writeOpenExtensionNames(open: string[]): void {
    if (!canUseStorage()) return;
    try {
        localStorage.setItem(OPEN_EXTENSIONS_STORAGE_KEY, JSON.stringify(open));
    } catch {
        // fail soft: in-memory accordion still works for this page load
    }
}
