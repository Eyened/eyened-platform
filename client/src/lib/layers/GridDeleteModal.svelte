<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { deleteFormAnnotation, formAnnotations } from "$lib/data";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import type { GridLayers } from "./gridLayers.svelte";

    // Carbon danger modal. It lives in the section, because a delete unmounts the row.
    let {
        grid,
        grids,
        open = $bindable(false),
        onfallback,
    }: {
        grid: FormAnnotationGET | null;
        grids: GridLayers;
        open?: boolean;
        /** Moves focus somewhere that still exists after the row is gone. */
        onfallback: () => void;
    } = $props();

    async function remove(target: FormAnnotationGET) {
        await deleteFormAnnotation(target.id);
        grids.forget(target.id);
    }

    function focusFallbackIfDeleted(event: Event) {
        if (grid && !formAnnotations.has(grid.id)) {
            event.preventDefault();
            onfallback();
        }
    }
</script>

<Modal
    bind:open
    danger
    size="xs"
    modalHeading="Delete grid"
    modalLabel={grid
        ? `ETDRS grid · ${grid.creator.name} [${grid.id}]`
        : undefined}
    primaryButtonText="Delete"
    primaryButtonLoadingDescription="Deleting…"
    successDescription="Deleted"
    errorTitle="Grid could not be deleted"
    onsubmit={() => (grid ? remove(grid) : false)}
    onCloseAutoFocus={focusFallbackIfDeleted}
>
    <p>Deletes the grid with its fovea and disc edge. This can't be undone.</p>
</Modal>
