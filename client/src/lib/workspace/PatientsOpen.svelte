<!--
@component
"N patients open": a status region, always mounted and empty with one patient, so a second patient is announced; not dismissible.
From xlg it reads "⚠ 2 patients open"; below, "⚠ 2", a 40 px button whose tooltip, on hover and on focus, says the rest.
-->
<script lang="ts">
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import WarningAltFilled from "carbon-icons-svelte/lib/WarningAltFilled.svelte";
    import { MediaQuery } from "svelte/reactivity";

    let { count }: { count: number } = $props();

    const xlg = new MediaQuery("min-width: 82rem");
    const text = $derived(count > 1 ? `${count} patients open` : "");
</script>

<span
    role="status"
    class={xlg.current
        ? "flex shrink-0 items-center gap-2 px-2 text-body-compact-01 whitespace-nowrap text-text-primary"
        : "sr-only"}
    >{#if text}{#if xlg.current}<WarningAltFilled
                aria-hidden="true"
                class="shrink-0 text-support-warning"
            />{/if}{text}{/if}</span
>
{#if text && !xlg.current}
    <!-- Outside the status region: it is the way to read the words without a screen reader (WCAG 1.4.13). -->
    <Tooltip.Provider delayDuration={100}>
        <Tooltip.Root>
            <Tooltip.Trigger
                aria-label={text}
                class="flex h-10 shrink-0 items-center gap-1 px-2 text-body-compact-01 text-text-primary hover:bg-background-hover"
            >
                <WarningAltFilled
                    aria-hidden="true"
                    class="text-support-warning"
                />{count}
            </Tooltip.Trigger>
            <Tooltip.Content size="icon">{text}</Tooltip.Content>
        </Tooltip.Root>
    </Tooltip.Provider>
{/if}
