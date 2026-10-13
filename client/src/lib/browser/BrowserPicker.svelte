<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";
    import Browser from "./Browser.svelte";
    import { BrowserContext, type Condition } from "./browserContext.svelte";

    // The image picker: the browser in a Carbon Modal lg. Focus trap, Escape and layering come with
    // the modal (B3, B14); a failed save keeps it open with the error and the selection (R1).
    interface Props {
        open?: boolean;
        // Conditions to seed the search with (e.g. Patient Identifier IN [...]).
        initialConditions?: Condition[];
        // Images that should already be selected when the picker opens.
        initialSelectedIds?: string[];
        /** Saves the selection; reject to keep the picker open with the error. */
        onConfirm: (ids: string[]) => Promise<void>;
        modalLabel?: string;
        errorTitle: string;
    }
    let {
        open = $bindable(false),
        initialConditions,
        initialSelectedIds,
        onConfirm,
        modalLabel,
        errorTitle,
    }: Props = $props();

    // The picker owns the context so it can read the selection back out.
    const context = new BrowserContext();
    context.urlSync = false;
</script>

<Modal
    bind:open
    size="lg"
    hasScrollingContent
    modalHeading="Browse images"
    {modalLabel}
    primaryButtonText="Save images"
    primaryButtonLoadingDescription="Saving images…"
    successDescription="Images saved"
    {errorTitle}
    onsubmit={() => onConfirm([...context.selectedIds])}
>
    <Browser
        {context}
        mode="overlay"
        syncUrl={false}
        {initialConditions}
        {initialSelectedIds}
    />
</Modal>
