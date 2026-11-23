<!--
@component
"n forms aren't complete" before a set is marked ready: Go back (focused, also Esc) changes nothing; the primary marks it ready anyway.
-->
<script lang="ts">
    import { Modal } from "$lib/components/ui/modal/index.js";

    let {
        setNumber,
        lines,
        last,
        onanswer,
    }: {
        setNumber: number;
        lines: string[];
        last: boolean;
        onanswer: (go: boolean) => void;
    } = $props();

    // Mounted per question, so each one starts open.
    let open = $state(true);
    const count = $derived(lines.length);
</script>

<Modal
    bind:open
    focusSecondary
    modalLabel="Set {setNumber}"
    modalHeading={count === 1
        ? "1 form isn't complete"
        : `${count} forms aren't complete`}
    primaryButtonText={last ? "Mark ready" : "Mark ready and next"}
    secondaryButtonText="Go back"
    primaryButtonLoadingDescription="Marking ready…"
    successDescription="Marked ready"
    errorTitle="Couldn't mark the set ready"
    onsubmit={() => {
        // The move goes on from here; no success state.
        onanswer(true);
        return false;
    }}
    onCloseAutoFocus={() => onanswer(false)}
>
    <ul class="list-disc ps-5">
        <!-- By index: two same-titled images give the same line. -->
        {#each lines.slice(0, 5) as line, i (i)}
            <li>{line}</li>
        {/each}
    </ul>
    {#if count > 5}
        <p class="mt-2">and {count - 5} more</p>
    {/if}
</Modal>
