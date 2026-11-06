<script lang="ts">
    import { Slider as SliderPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    // Carbon Slider without number inputs (Slider, Specifications): 4 px track; one handle 14 px, 20 px while active; two handles 16 px.
    // One handle or two. Vertical runs top to bottom. Pass values on the step grid: bits-ui rewrites any other value.
    let {
        values,
        onchange,
        oncommit,
        min,
        max,
        step = 1,
        labels,
        valueTexts,
        orientation = "horizontal",
        fill = true,
        class: className,
    }: {
        values: number[];
        onchange: (values: number[]) => void;
        oncommit?: () => void;
        min: number;
        max: number;
        step?: number;
        labels: string[];
        valueTexts?: string[];
        orientation?: "horizontal" | "vertical";
        fill?: boolean;
        class?: string;
    } = $props();

    const vertical = $derived(orientation === "vertical");
</script>

<SliderPrimitive.Root
    type="multiple"
    bind:value={() => values, onchange}
    onValueCommit={oncommit}
    {min}
    {max}
    {step}
    {orientation}
    dir={vertical ? "rtl" : "ltr"}
    thumbPositioning="exact"
    class={cn(
        "group/slider relative flex items-center justify-center select-none",
        vertical ? "h-full w-3.5" : "h-6 w-full",
        className,
    )}
>
    {#snippet children({ thumbItems })}
        <span
            class={cn(
                "relative block overflow-hidden bg-border-subtle-01",
                vertical ? "h-full w-1" : "h-1 w-full",
                !fill &&
                    "group-has-focus-visible/slider:bg-interactive group-has-data-active/slider:bg-interactive",
            )}
        >
            {#if fill}
                <SliderPrimitive.Range
                    class="absolute bg-border-inverse group-has-focus-visible/slider:bg-interactive group-has-data-active/slider:bg-interactive data-[orientation=horizontal]:h-full data-[orientation=vertical]:w-full"
                />
            {/if}
        </span>
        {#each thumbItems as { index } (index)}
            <SliderPrimitive.Thumb
                {index}
                aria-label={labels[index]}
                aria-valuetext={valueTexts?.[index]}
                class={cn(
                    "z-1 block cursor-pointer rounded-full bg-icon-primary focus-visible:border-2 focus-visible:border-focus focus-visible:shadow-button-focus data-active:bg-interactive",
                    values.length === 2
                        ? "size-4"
                        : "size-3.5 data-active:size-5",
                )}
            />
        {/each}
    {/snippet}
</SliderPrimitive.Root>
