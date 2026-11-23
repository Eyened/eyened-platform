import { createFormAnnotation } from "$lib/data";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import {
    closeFormWindow,
    fillFormWindow,
    openBlankFormWindow,
} from "$lib/viewer-window/panelForm/openFormInNewWindow";
import { tick } from "svelte";
import type { FormAnnotationGET } from "../../types/openapi_types";

export interface CreateRequest {
    /** One create per key at a time: "grade:<target>", "add", "copy:<form id>". */
    key: string;
    schemaName: string;
    /** The status message without ", opened in window". */
    message: string;
    payload: Parameters<typeof createFormAnnotation>[0];
    viewerContext?: ViewerContext;
}

/** Grade, Add form and Copy: open the window inside the click, create, then fill the window. */
export class FormCreator {
    /** The schema whose create failed, until the next create works or the notice closes. */
    failed: string | null = $state(null);
    /** Announced after each create that works. */
    message = $state("");
    // eslint-disable-next-line svelte/prefer-svelte-reactivity -- only create() reads it, never a template
    private readonly running = new Set<string>();
    private failedControl: HTMLElement | null = null;

    async create(request: CreateRequest): Promise<FormAnnotationGET | null> {
        if (this.running.has(request.key)) return null;
        this.running.add(request.key);
        const control =
            document.activeElement instanceof HTMLElement
                ? document.activeElement
                : null;
        // Before the first await, so the browser counts the click and doesn't block the window.
        const win = openBlankFormWindow();
        let form: FormAnnotationGET;
        try {
            form = await createFormAnnotation(request.payload);
        } catch {
            if (win) closeFormWindow(win);
            this.failed = request.schemaName;
            this.failedControl = control;
            return null;
        } finally {
            this.running.delete(request.key);
        }
        this.failed = null;
        if (win) fillFormWindow(win, form, true, request.viewerContext);
        const opened = win !== null && !win.closed;
        // Cleared first, so the same message twice (two copies) is announced twice.
        this.message = "";
        await tick();
        this.message = opened
            ? `${request.message}, opened in window`
            : request.message;
        return form;
    }

    /** The notice's close button: focus goes back to the control that failed. */
    dismiss(): void {
        this.failed = null;
        this.failedControl?.focus();
        this.failedControl = null;
    }
}
