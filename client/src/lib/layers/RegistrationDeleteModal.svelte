<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { deleteFormAnnotation, formAnnotations } from "$lib/data";
    import type { FormAnnotationGET } from "../../types/openapi_types";

    // Carbon danger modal. It lives in the section, because a delete unmounts the row.
    let {
        registration,
        open = $bindable(false),
        onfallback,
    }: {
        registration: FormAnnotationGET | null;
        open?: boolean;
        /** Moves focus somewhere that still exists after the row is gone. */
        onfallback: () => void;
    } = $props();

    function focusFallbackIfDeleted(event: Event) {
        if (registration && !formAnnotations.has(registration.id)) {
            event.preventDefault();
            onfallback();
        }
    }
</script>

<Modal
    bind:open
    danger
    size="xs"
    modalHeading="Delete registration"
    modalLabel={registration ? `Registration [${registration.id}]` : undefined}
    primaryButtonText="Delete"
    primaryButtonLoadingDescription="Deleting…"
    successDescription="Deleted"
    errorTitle="Registration could not be deleted"
    onsubmit={() =>
        registration ? deleteFormAnnotation(registration.id) : false}
    onCloseAutoFocus={focusFallbackIfDeleted}
>
    <!-- ASSUMPTION: the spec gives no consequence line. -->
    <p>
        Deletes the registration and its points on every image. This can't be
        undone.
    </p>
</Modal>
