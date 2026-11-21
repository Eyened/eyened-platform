/** Where focus goes once a row is deleted: the next row's first control, else the previous row's, else its section header. Read before the delete, while the row is still there; `section` is the fallback when the row is not on screen. */
export function focusAfterDelete(
    row: Element | null,
    section: Element | null,
): () => void {
    const li = row?.closest("li");
    const first = (el: Element | null | undefined) =>
        el?.querySelector<HTMLElement>("[data-layer-row] button") ?? null;
    const header = (
        row?.closest("[data-layer-section]") ?? section
    )?.querySelector<HTMLElement>("button");
    const target =
        first(li?.nextElementSibling) ??
        first(li?.previousElementSibling) ??
        header ??
        null;
    return () => target?.focus();
}
