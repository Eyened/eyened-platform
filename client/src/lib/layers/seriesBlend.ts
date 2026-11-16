import { seriesBlendWeights } from "$lib/viewer-window/panelRegistration/seriesBlendWeights";

/** Starting ticks: this image and the same-modality images nearest it by date, up to `cap`; the earlier wins a tie. */
export function defaultTicks(
    items: readonly { id: string; date: string; modality: string }[],
    thisId: string,
    cap: number,
): string[] {
    const self = items.find((item) => item.id === thisId);
    if (!self) return [thisId];
    const day = (date: string) => Date.parse(date) || 0;
    const away = (date: string) => Math.abs(day(date) - day(self.date));
    const nearest = items
        .filter((item) => item.id !== thisId && item.modality === self.modality)
        .sort(
            (a, b) => away(a.date) - away(b.date) || day(a.date) - day(b.date),
        )
        .slice(0, Math.max(0, cap - 1));
    return [thisId, ...nearest.map((item) => item.id)];
}

/** Series weights from a slider over the images oldest first, returned in layer order: this image first. */
export function seriesLayerWeights(
    datedIds: readonly string[],
    thisId: string,
    position: number,
): number[] {
    const n = datedIds.length;
    const weights = seriesBlendWeights(n > 1 ? position / (n - 1) : 0, n);
    const self = datedIds.indexOf(thisId);
    return [weights[self] ?? 0, ...weights.filter((_, i) => i !== self)];
}

/** The next whole image from a slider position, within 0 … count − 1. */
export function nextStop(
    position: number,
    direction: 1 | -1,
    count: number,
): number {
    const stop =
        direction > 0 ? Math.floor(position) + 1 : Math.ceil(position) - 1;
    return Math.min(Math.max(stop, 0), Math.max(count - 1, 0));
}
