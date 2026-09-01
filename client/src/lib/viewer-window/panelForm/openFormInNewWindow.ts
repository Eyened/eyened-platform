import { openNewWindow } from "$lib/newWindow";
import { formSchemas } from "$lib/data/stores.svelte";
import { pointArming } from "$lib/forms/pointArming.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { FormAnnotationGET } from "../../../types/openapi_types";
import FormItemContent from "./FormItemContent.svelte";

let openWindow: Window | null = null;

export function openFormInNewWindow(
    form: FormAnnotationGET,
    canEdit: boolean,
    viewerContext?: ViewerContext,
): Window {
    if (openWindow) {
        openWindow.close();
        pointArming.disarm();
    }
    const formSchema = formSchemas.get(form.form_schema_id);
    const title = formSchema
        ? `${formSchema.name} ${form.id}`
        : `Form ${form.id}`;

    openWindow = openNewWindow(
        // @ts-expect-error - openNewWindow has loose typing for component props
        FormItemContent,
        { form, canEdit, viewerContext },
        title,
    );

    if (openWindow) {
        openWindow.addEventListener("beforeunload", () => {
            pointArming.disarm();
            openWindow = null;
        });
    }

    return openWindow;
}
