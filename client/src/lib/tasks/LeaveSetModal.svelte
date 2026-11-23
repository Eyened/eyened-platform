<!--
@component
"Leave set n without saving": Stay (focused, also Esc) keeps the grader in the set; Leave goes without marking it ready.
-->
<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";

    let {
        setNumber,
        markReady,
        onanswer,
    }: {
        setNumber: number;
        markReady: boolean;
        onanswer: (leave: boolean) => void;
    } = $props();

    // Mounted per question, so each one starts open.
    let open = $state(true);
</script>

<Modal
    bind:open
    danger
    modalHeading="Leave set {setNumber} without saving"
    primaryButtonText="Leave set {setNumber}"
    secondaryButtonText="Stay in set {setNumber}"
    primaryButtonLoadingDescription="Leaving…"
    successDescription="Leaving…"
    errorTitle="Couldn't leave the set"
    onsubmit={() => {
        onanswer(true);
        // The page load follows; no success state.
        return false;
    }}
    onCloseAutoFocus={(event) => {
        // Stay moves focus to what didn't save, not back to the button.
        event.preventDefault();
        onanswer(false);
    }}
>
    <p>
        Some of your work in set {setNumber} isn't saved.{#if markReady}
            Set {setNumber} won't be marked ready.{/if}
    </p>
</Modal>
