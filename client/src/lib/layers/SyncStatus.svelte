<!--
@component
The current row's save state: a dot and its text.
-->
<script lang="ts">
    import type { SyncState } from "$lib/webgl/segmentationState.svelte";

    let { sync }: { sync: SyncState } = $props();

    const TEXT: Record<SyncState, string> = {
        synced: "Saved",
        saving: "Saving…",
        error: "Couldn't save",
    };
    const DOT: Record<SyncState, string> = {
        synced: "bg-support-success",
        saving: "bg-support-warning",
        error: "bg-support-error",
    };
</script>

<p class="flex items-center gap-2 text-helper-text-01 text-text-secondary">
    <span class="size-2 rounded-full {DOT[sync]}" aria-hidden="true"></span>
    {TEXT[sync]}
</p>
