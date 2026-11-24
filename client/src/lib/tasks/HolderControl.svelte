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
        /** The task shows the status menu; below xlg Claim / Give back are its last item. */
        showStatus: boolean;
    } = $props();

    // Below xlg (82rem), with status on, the action moves into ▾.
    const xlg = new MediaQuery("min-width: 82rem");
    const claimInMenu = $derived(showStatus && !xlg.current);

    const LABELS = { claim: "Claim", giveBack: "Give back" } as const;
</script>

<!-- The header squeezes the tag first; it stops at 80 px and cuts the name, which its title shows. -->
<!-- ASSUMPTION: min-w-20 (80 px) is the smallest the tag gets. -->
<div class="flex min-w-0 items-center gap-1">
    <!-- A live region: quiet on load, it reads the new holder after Claim, Give back or a save that claims. -->
    <span role="status" class="flex min-w-20">
        <Tag icon={User} title={holder.text} class="max-w-[min(13rem,100%)]"
            >{holder.text}</Tag
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
