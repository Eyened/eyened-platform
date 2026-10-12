<script lang="ts">
    import { Progress } from "$lib/components/ui/progress/index.js";
    import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";

    // Carbon ProgressBar, small (4 px) only; values from @carbon/styles 1.117.0 progress-bar,
    // markup from @carbon/react 1.118.0: finished fills the bar and put the status icon in
    // the label row (hidden with the label when hideLabel is set).
    const uid = $props.id();
    let {
        labelText,
        hideLabel = false,
        helperText,
        value,
        max = 100,
        status = "active",
    }: {
        labelText: string;
        hideLabel?: boolean;
        helperText?: string;
        value: number;
        max?: number;
        status?: "active" | "finished";
    } = $props();

    const filled = $derived(status === "finished" ? max : value);
</script>

<div class="min-w-12">
    <div
        id="{uid}-label"
        class={hideLabel
            ? "sr-only"
            : "mb-2 flex justify-between text-body-compact-01 text-text-primary"}
    >
        <span class="truncate">{labelText}</span>
        {#if status === "finished"}
            <CheckmarkFilled
                data-slot="progress-bar-status-icon"
                class="ml-4 shrink-0 text-support-success"
            />
        {/if}
    </div>
    <Progress
        value={filled}
        {max}
        class="h-1"
        indicatorClass={status === "finished"
            ? "bg-support-success"
            : undefined}
        aria-busy={status !== "finished"}
        aria-labelledby="{uid}-label"
        aria-describedby={helperText ? `${uid}-helper` : undefined}
    />
    {#if helperText}
        <div
            id="{uid}-helper"
            class="mt-2 text-helper-text-01 text-text-secondary"
        >
            {helperText}
        </div>
    {/if}
</div>
