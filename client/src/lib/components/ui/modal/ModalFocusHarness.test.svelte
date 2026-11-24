<script lang="ts">
    import { BitsConfig } from "bits-ui";
    import { createRawSnippet } from "svelte";
    import Modal from "./modal.svelte";

    let { portalTo }: { portalTo: Element } = $props();
    let open = $state(false);
    const body = createRawSnippet(() => ({ render: () => "<p>Body</p>" }));
</script>

<BitsConfig defaultPortalTo={portalTo}>
    <button onclick={() => (open = true)}>Trigger</button>
    <Modal
        bind:open
        modalHeading="Edit"
        primaryButtonText="Save"
        primaryButtonLoadingDescription="Saving"
        successDescription="Saved"
        errorTitle="Failed"
        onsubmit={() => false}
        children={body}
    />
</BitsConfig>
