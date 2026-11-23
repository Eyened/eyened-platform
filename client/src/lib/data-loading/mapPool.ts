/**
 * Run ``fn`` over ``items`` with at most ``concurrency`` in flight.
 * Results keep input order.
 */
export async function mapPool<T, R>(
    items: readonly T[],
    concurrency: number,
    fn: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
    if (items.length === 0) {
        return [];
    }
    const limit = Math.max(1, Math.min(concurrency, items.length));
    const results = new Array<R>(items.length);
    let next = 0;

    async function worker(): Promise<void> {
        while (true) {
            const i = next++;
            if (i >= items.length) {
                return;
            }
            results[i] = await fn(items[i], i);
        }
    }

    await Promise.all(Array.from({ length: limit }, () => worker()));
    return results;
}

/** Cap workers used for parallel J2K frame decode. */
export function dicomDecodeConcurrency(): number {
    const cores =
        typeof navigator !== "undefined" ? navigator.hardwareConcurrency : 4;
    return Math.min(8, Math.max(2, cores || 4));
}
