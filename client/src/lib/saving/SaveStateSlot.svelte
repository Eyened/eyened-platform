<!--
@component
The header's save state: nothing before the first edit, then Saving…, Saved, or what couldn't save as a button to it.
Below xlg only its icon shows, with the words in a tooltip and in hidden text. The icon is a tab stop then, so the tooltip opens on focus as well as hover. S2 Tooltip: "Tooltips must be placed on focusable elements… Use ContextualHelp to provide context for non-interactive elements such as plain text"; a focusable status is a recorded deviation.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";
    import ErrorFilled from "carbon-icons-svelte/lib/ErrorFilled.svelte";
    import { saveTracker } from "./saveTracker.svelte";

    let { iconOnly }: { iconOnly: boolean } = $props();
    const text = $derived(saveTracker.text);
    const state = $derived(saveTracker.worst);

    function revealFirst() {
        const first = saveTracker.firstUnsaved();
        if (first) saveTracker.reveal(first);
    }
</script>

<!-- Always mounted, so a change is announced; the width is kept from the start. -->
<!-- ASSUMPTION: min-w-40 (160 px) holds "Saving…" and "Saved"; a failure's longer words may widen it. -->
<div
    role="status"
    class="flex shrink-0 items-center {iconOnly
        ? 'w-10 justify-center'
        : 'min-w-40 justify-end'}"
>
    {#if text && state === "error"}
        {#if iconOnly}
            <IconButton label={text} onclick={revealFirst}>
                <ErrorFilled class="text-status-red" />
                <!-- The live region needs text, not only the button's label, to announce the failure. -->
                <span class="sr-only">{text}</span>
            </IconButton>
        {:else}
            <Button variant="ghost" size="sm" onclick={revealFirst}>
                <ErrorFilled aria-hidden="true" class="text-status-red" />
                {text}
            </Button>
        {/if}
    {:else if text}
        <Tooltip.Provider delayDuration={100}>
            <Tooltip.Root disabled={!iconOnly}>
                <Tooltip.Trigger>
                    {#snippet child({ props })}
                        <!-- Set after the spread: a tab stop only while the words are hidden, so keyboard users can open the tooltip. -->
                        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
                        <span
                            {...props}
                            tabindex={iconOnly ? 0 : -1}
                            class="inline-flex items-center gap-2 px-2 text-body-compact-01 text-text-secondary"
                        >
                            {#if state === "saving"}
                                <!-- Hidden: its "Loading" name would be read before "Saving…". -->
                                <span aria-hidden="true" class="inline-flex">
                                    <InlineLoading
                                        class="min-h-0 w-auto"
                                        status="active"
                                        live={false}
                                    />
                                </span>
                            {:else}
                                <CheckmarkFilled
                                    aria-hidden="true"
                                    class="text-status-green"
                                />
                            {/if}
                            <span class={iconOnly ? "sr-only" : undefined}
                                >{text}</span
                            >
                        </span>
                    {/snippet}
                </Tooltip.Trigger>
                <Tooltip.Content size="icon">{text}</Tooltip.Content>
            </Tooltip.Root>
        </Tooltip.Provider>
    {/if}
</div>
