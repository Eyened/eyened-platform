<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";
    import {
        deleteFormAnnotation,
        formAnnotations,
        formSchemas,
    } from "$lib/data";
    import { dropFormAnnotationSaver } from "$lib/saving/formAnnotationSavers";
    import type { FormAnnotationGET } from "../../../types/openapi_types";
    import { closeFormWindowFor } from "./openFormInNewWindow";

    // Carbon danger modal for deleting a saved form. It lives in the list, because a delete unmounts the card.
    let {
        form,
        open = $bindable(false),
        fallback,
        onfallback,
    }: {
        form: FormAnnotationGET | null;
        open?: boolean;
        fallback?: HTMLElement;
        /** Moves focus itself, for lists that pick the next row; used instead of `fallback`. */
        onfallback?: () => void;
    } = $props();

    // The window and the saver go with the form, so no save is sent to the deleted id.
    async function remove(id: number) {
        await deleteFormAnnotation(id);
        closeFormWindowFor(id);
        dropFormAnnotationSaver(id);
    }

    // The deleted form's card is gone, so focus moves to the list's fallback element.
    function focusFallbackIfDeleted(event: Event) {
        if (form && !formAnnotations.has(form.id)) {
            event.preventDefault();
            if (onfallback) onfallback();
            else fallback?.focus();
        }
    }
</script>

<Modal
    bind:open
    danger
    size="xs"
    modalHeading="Delete form"
    modalLabel={form
        ? `${formSchemas.get(form.form_schema_id)?.name} ${form.id}`
        : undefined}
    primaryButtonText="Delete"
    primaryButtonLoadingDescription="Deleting…"
    successDescription="Deleted"
    errorTitle="Form could not be deleted"
    onsubmit={() => (form ? remove(form.id) : false)}
    onCloseAutoFocus={focusFallbackIfDeleted}
>
    <p>Deletes the form and its answers. This can't be undone.</p>
</Modal>
