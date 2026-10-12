<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { TextArea } from "$lib/components/ui/text-area/index.js";
    import { updateSubTaskComments } from "$lib/data/helpers";
    import { untrack } from "svelte";
    import type { SubTaskWithImagesGET } from "../../types/openapi_types";

    // One per table. The server assigns an unassigned subtask to whoever saves its comments.
    type Props = {
        open?: boolean;
        subtask: SubTaskWithImagesGET | null;
        /** A save succeeded; the page refreshes rows and assignees. */
        onchange: () => void;
        onCloseAutoFocus: (event: Event) => void;
    };
    let {
        open = $bindable(false),
        subtask,
        onchange,
        onCloseAutoFocus,
    }: Props = $props();

    let draft = $state("");

    // Each open starts from the stored comments.
    $effect(() => {
        if (open) draft = untrack(() => subtask?.comments ?? "");
    });

    const unassigned = $derived(
        subtask !== null && subtask.creator_id == null && !subtask.creator,
    );

    function save() {
        if (!subtask) return false;
        if (draft === (subtask.comments ?? "")) {
            open = false;
            return false;
        }
        return updateSubTaskComments(subtask.id, draft).then(() => onchange());
    }
</script>

<Modal
    bind:open
    modalHeading="Edit comments"
    modalLabel={subtask ? `Set ${subtask.index}` : undefined}
    primaryButtonText="Save"
    primaryButtonLoadingDescription="Saving…"
    successDescription="Saved"
    errorTitle="Comments could not be saved"
    onsubmit={save}
    {onCloseAutoFocus}
>
    <TextArea
        labelText="Comments"
        bind:value={draft}
        helperText={unassigned
            ? "Saving also assigns this set to you."
            : undefined}
    />
</Modal>
