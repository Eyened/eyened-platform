/** A one-row roving tab stop: the index a key moves focus to, or null for a key it doesn't handle. */
export function rovingIndex(
    key: string,
    i: number,
    count: number,
    keys: { prev: readonly string[]; next: readonly string[] },
): number | null {
    if (keys.next.includes(key)) return Math.min(i + 1, count - 1);
    if (keys.prev.includes(key)) return Math.max(i - 1, 0);
    if (key === "Home") return 0;
    if (key === "End") return count - 1;
    return null;
}
