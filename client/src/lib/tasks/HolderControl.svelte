<!--
@component
Who holds the set, as a read-only Tag, and beside it Claim or Give back as a ghost button unless they sit in ▾.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import User from "carbon-icons-svelte/lib/User.svelte";
    import { MediaQuery } from "svelte/reactivity";
    import type { SetHolder } from "./holder.svelte";

    let {
        holder,
        showStatus,
    }: {
        holder: SetHolder;
        /** The task shows the status menu; below lg Claim / Give back are its last item. */
        showStatus: boolean;
    } = $props();

    // Below lg (66rem) the tag shrinks to fit, and with status on the action moves into ▾.
    const lg = new MediaQuery("min-width: 66rem");
    const compact = $derived(!lg.current);
    const claimInMenu = $derived(showStatus && compact);

    const LABELS = { claim: "Claim", giveBack: "Give back" } as const;
</script>

<!-- No min-w-0: the tag's minimum holds the wrapper's, so the header can't squeeze the tag below it. -->
<div class="flex items-center gap-1">
    <!-- A live region: quiet on load, it reads the new holder after Claim, Give back or a save that claims. -->
    <span role="status" class="flex">
        <!-- ASSUMPTION: min-w-20 (80 px) is the smallest the tag gets below lg. -->
        <Tag
            icon={User}
            title={holder.text}
            class={compact ? "min-w-20" : undefined}>{holder.text}</Tag
        >
    </span>
    {#if holder.action && !claimInMenu}
        <!-- One button whose words change, so focus stays on it after Claim or Give back. -->
        <Button
            variant="ghost"
            size="sm"
            aria-disabled={holder.busy || undefined}
            onclick={() => void holder.run()}
        >
            {#if holder.busy}
                <InlineLoading
                    class="text-inherit"
                    status="active"
                    description={LABELS[holder.action]}
                    live={false}
                />
            {:else}
                {LABELS[holder.action]}
            {/if}
        </Button>
        <!-- Always mounted, so the text is announced when it appears. -->
        <span
            role="alert"
            class="text-helper-text-01 whitespace-nowrap text-text-error"
            >{holder.failText}</span
        >
    {/if}
</div>
