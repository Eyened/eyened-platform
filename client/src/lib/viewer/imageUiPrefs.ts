const STORAGE_KEY = "eyened:imageUiPrefs";

type ImageUiPrefs = Record<string, Record<string, unknown>>;

function canUseStorage(): boolean {
    try {
        return typeof localStorage !== "undefined";
    } catch {
        return false;
    }
}

function readAll(): ImageUiPrefs {
    if (!canUseStorage()) return {};
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return {};
        const parsed = JSON.parse(raw) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            return {};
        }
        return parsed as ImageUiPrefs;
    } catch {
        return {};
    }
}

export function getImageUiPref<T>(
    imageId: string,
    key: string,
    defaultValue: T,
): T {
    const value = readAll()[imageId]?.[key];
    return value === undefined ? defaultValue : (value as T);
}

export function setImageUiPref(
    imageId: string,
    key: string,
    value: unknown,
): void {
    if (!canUseStorage()) return;
    const all = readAll();
    all[imageId] = { ...all[imageId], [key]: value };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
}

/** The segmentation opacity saved for an image; 1 when none is saved or the value is bad. */
export function readOpacity(imageId: string): number {
    const value = getImageUiPref<unknown>(imageId, "opacity", 1);
    return typeof value === "number" && value >= 0 && value <= 1 ? value : 1;
}

export function writeOpacity(imageId: string, value: number): void {
    setImageUiPref(imageId, "opacity", value);
}
