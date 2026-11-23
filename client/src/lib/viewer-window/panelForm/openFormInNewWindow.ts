import { mountInWindow, openBlankWindow } from "$lib/newWindow";
import { formSchemas } from "$lib/data/stores.svelte";
import { pointArming } from "$lib/forms/pointArming.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { FormAnnotationGET } from "../../../types/openapi_types";
import FormItemContent from "./FormItemContent.svelte";
import { openForm } from "./openForm.svelte";

let openWindow: Window | null = null;

function forget(win: Window): void {
    if (openWindow !== win) return;
    openWindow = null;
    openForm.id = null;
    pointArming.disarm();
}

/** Closes the open window and opens a blank one in its place; call it inside the click. */
export function openBlankFormWindow(): Window | null {
    if (openWindow) closeFormWindow(openWindow);
    // The old window's unload may run after this, so nothing stays marked open meanwhile.
    openForm.id = null;
    openWindow = openBlankWindow();
    return openWindow;
}

/** Shows the form in a window from openBlankFormWindow, unless the grader closed it meanwhile. */
export function fillFormWindow(
    win: Window,
    form: FormAnnotationGET,
    canEdit: boolean,
    viewerContext?: ViewerContext,
): void {
    if (win.closed || win !== openWindow) {
        forget(win);
        return;
    }
    const formSchema = formSchemas.get(form.form_schema_id);
    const title = formSchema
        ? `${formSchema.name} ${form.id}`
        : `Form ${form.id}`;
    mountInWindow(
        win,
        // @ts-expect-error - mountInWindow has loose typing for component props
        FormItemContent,
        { form, canEdit, viewerContext },
        title,
    );
    // A window closed earlier may unload late; only the open one clears the mark.
    win.addEventListener("beforeunload", () => forget(win));
    openForm.id = form.id;
}

export function closeFormWindow(win: Window): void {
    win.close();
    forget(win);
}

/** After a delete: the window goes if it shows that form. */
export function closeFormWindowFor(formId: number): void {
    if (openWindow && openForm.id === formId) closeFormWindow(openWindow);
}

export function openFormInNewWindow(
    form: FormAnnotationGET,
    canEdit: boolean,
    viewerContext?: ViewerContext,
): Window | null {
    const win = openBlankFormWindow();
    if (win) fillFormWindow(win, form, canEdit, viewerContext);
    return win;
}
