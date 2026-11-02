import { getContext, setContext } from "svelte";

const key = Symbol("dialog-content");

/** Called by `Dialog.Content` so descendants can mount onto its box. */
export function setDialogContentElement(get: () => HTMLElement | null) {
    setContext(key, get);
}

/** The enclosing dialog content element, or null outside a dialog. */
export function getDialogContentElement(): HTMLElement | null {
    return getContext<(() => HTMLElement | null) | undefined>(key)?.() ?? null;
}
