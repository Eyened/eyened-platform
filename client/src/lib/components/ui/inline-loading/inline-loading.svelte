<script lang="ts">
    import { cn } from "$lib/utils.js";
    import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";

    // Carbon InlineLoading, active and finished states; values from @carbon/styles 1.117.0
    // inline-loading and loading, spinner markup from Carbon React Loading.tsx (small).
    // Like Carbon React, the description is optional; without one the spinner svg is named "Loading" by its <title>.
    let {
        status,
        description,
        class: className,
    }: {
        status: "active" | "finished";
        description?: string;
        class?: string;
    } = $props();
</script>

<div
    data-slot="inline-loading"
    aria-live="assertive"
    class={cn(
        "flex min-h-8 w-full items-center text-body-compact-01 text-text-secondary",
        className,
    )}
>
    <div
        class={cn(
            "relative flex items-center justify-center",
            description && "mr-2",
        )}
    >
        {#if status === "active"}
            <svg
                viewBox="0 0 100 100"
                class="size-4 animate-loading-rotate fill-none"
                aria-hidden={description ? "true" : undefined}
            >
                {#if !description}<title>Loading</title>{/if}
                <circle
                    cx="50%"
                    cy="50%"
                    r="42"
                    stroke-width="16"
                    class="stroke-layer-accent-01"
                />
                <circle
                    cx="50%"
                    cy="50%"
                    r="42"
                    stroke-width="16"
                    stroke-dasharray="276.4608 276.4608"
                    stroke-dashoffset="143.759616"
                    class="stroke-interactive"
                />
            </svg>
        {:else}
            <CheckmarkFilled aria-hidden="true" class="text-support-success" />
        {/if}
    </div>
    {#if description}<span>{description}</span>{/if}
</div>
