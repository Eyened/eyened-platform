<script lang="ts">
    import { Progress } from "$lib/components/ui/progress/index.js";

    // Carbon ProgressBar, small (4 px) only; values from @carbon/styles 1.117.0 progress-bar.
    const uid = $props.id();
    let {
        labelText,
        hideLabel = false,
        helperText,
        value,
        max = 100,
    }: {
        labelText: string;
        hideLabel?: boolean;
        helperText?: string;
        value: number;
        max?: number;
    } = $props();
</script>

<div class="min-w-12">
    <div
        id="{uid}-label"
        class={hideLabel
            ? "sr-only"
            : "mb-2 text-body-compact-01 text-text-primary"}
    >
        {labelText}
    </div>
    <Progress
        {value}
        {max}
        class="h-1"
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
