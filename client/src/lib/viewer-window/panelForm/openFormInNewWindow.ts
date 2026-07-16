import { openNewWindow } from "$lib/newWindow";
import { formSchemas } from "$lib/data/stores.svelte";
import type { FormAnnotationGET } from "../../../types/openapi_types";
import FormItemContent from "./FormItemContent.svelte";

let openWindow: Window | null = null;

export function openFormInNewWindow(
    form: FormAnnotationGET,
    canEdit: boolean,
): Window {
    if (openWindow) {
        openWindow.close();
    }
    const formSchema = formSchemas.get(form.form_schema_id);
    const title = formSchema
        ? `${formSchema.name} ${form.id}`
        : `Form ${form.id}`;

    openWindow = openNewWindow(
        // @ts-expect-error - openNewWindow has loose typing for component props
        FormItemContent,
        { form, canEdit },
        title,
    );
    return openWindow;
}
