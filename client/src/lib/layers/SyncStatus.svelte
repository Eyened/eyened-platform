<!--
@component
A pane's save state: an icon and its text, then Retry after a failed save. Not a live region: the header's save state announces.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import type { SaveState } from "$lib/saving/saveTracker.svelte";
    import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";
    import ErrorFilled from "carbon-icons-svelte/lib/ErrorFilled.svelte";

    let { sync, onretry }: { sync: SaveState; onretry?: () => void } = $props();
</script>

<!-- Carbon icon indicators: in progress, succeeded, failed. -->
<div class="flex items-center gap-2 text-helper-text-01 text-text-secondary">
    {#if sync === "saving"}
        <InlineLoading
            class="min-h-0 w-auto text-helper-text-01"
            status="active"
            description="Saving…"
            live={false}
        />
    {:else if sync === "synced"}
        <span class="inline-flex items-center gap-2">
            <CheckmarkFilled aria-hidden="true" class="text-status-green" />
            Saved
        </span>
    {:else}
        <span class="inline-flex items-center gap-2">
            <ErrorFilled aria-hidden="true" class="text-status-red" />
            Couldn't save
        </span>
        {#if onretry}
            <!-- The one Retry in the panel: reveal focuses it. -->
            <Button variant="ghost" size="sm" data-save-retry onclick={onretry}
                >Retry</Button
            >
        {/if}
    {/if}
</div>
