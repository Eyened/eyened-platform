import { focusAfterDelete } from "$lib/layers/focusAfterDelete";

/** Focus after a form row's delete; a group whose only form went disappears with its header, so then the section around it, else Add form. */
export function focusAfterFormDelete(control: HTMLElement): () => void {
    const group = control.closest("[data-layer-section]");
    const next = focusAfterDelete(control.closest("[data-layer-row]"), group);
    const panel = control.closest("[data-forms-panel]");
    const outer =
        group?.parentElement
            ?.closest("[data-layer-section]")
            ?.querySelector<HTMLElement>("button") ??
        panel?.querySelector<HTMLElement>("[data-add-form]") ??
        null;
    return () => {
        next();
        // The next row or the group's header may be gone by the time the modal closes.
        if (!panel?.contains(document.activeElement)) outer?.focus();
    };
}
