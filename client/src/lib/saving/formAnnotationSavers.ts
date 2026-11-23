import { putFormAnnotationValue, storeFormAnnotationValue } from "$lib/data";
import { SvelteMap } from "svelte/reactivity";
import { DebouncedSaver } from "./debouncedSaver.svelte";
import type { RevealTarget } from "./saveTracker.svelte";

/** One saver per form annotation on the page, whichever viewport or window edits it. */
export const formAnnotationSavers = new SvelteMap<
    number,
    DebouncedSaver<unknown>
>();

/** The annotation's saver; the first caller names its kind, the latest caller where its Retry is. */
// ASSUMPTION: the form window never edits a registration or ETDRS annotation (their built-in schemas are hidden from it by HIDE_FROM_FORM_PANEL_NAMES), so the first caller's kind, delay and store write fit every caller.
export function formAnnotationSaver(
    id: number,
    kind: "form" | "registration" | "ETDRS grid",
    target: RevealTarget,
): DebouncedSaver<unknown> {
    let saver = formAnnotationSavers.get(id);
    if (!saver) {
        saver = new DebouncedSaver<unknown>({
            kind,
            group: `form-annotation-${id}`,
            target,
            // The form window waits for typing to pause; the point tools save on release.
            delay: kind === "form" ? 500 : 0,
            send: async (value) => putFormAnnotationValue(id, value),
            // The point tools write the store as they move; the form window's value reaches it once saved.
            onSaved:
                kind === "form"
                    ? (value) => storeFormAnnotationValue(id, value)
                    : undefined,
        });
        formAnnotationSavers.set(id, saver);
    }
    // A reopened form window or a rebound viewport: Retry goes to the one open now.
    saver.target = target;
    return saver;
}
