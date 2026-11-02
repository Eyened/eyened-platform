<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";
    import {
        deleteFormAnnotation,
        formAnnotations,
        formSchemas,
    } from "$lib/data";
    import type { FormAnnotationGET } from "../../../types/openapi_types";

    // Carbon danger modal for deleting a saved form. It lives in the list, because a delete unmounts the card.
    let {
        form,
        open = $bindable(false),
        fallback,
    }: {
        form: FormAnnotationGET | null;
        open?: boolean;
        fallback: HTMLElement | undefined;
    } = $props();

    // The deleted form's card is gone, so focus moves to the list's fallback element.
    function focusFallbackIfDeleted(event: Event) {
        if (form && !formAnnotations.has(form.id)) {
            event.preventDefault();
            fallback?.focus();
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
    onsubmit={() => (form ? deleteFormAnnotation(form.id) : false)}
    onCloseAutoFocus={focusFallbackIfDeleted}
>
    <p>Deletes the form and its answers. This can't be undone.</p>
</Modal>
