<script lang="ts">
    import { Calendar as CalendarPrimitive } from "bits-ui";
    import ChevronLeft from "carbon-icons-svelte/lib/ChevronLeft.svelte";
    import { cn } from "$lib/utils.js";

    // Carbon .flatpickr-prev-month: 40 px, hover layer-hover-01.
    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: CalendarPrimitive.PrevButtonProps = $props();
</script>

{#snippet Fallback()}
    <ChevronLeft />
{/snippet}

<CalendarPrimitive.PrevButton
    bind:ref
    class={cn(
        "flex size-10 cursor-pointer items-center justify-center text-icon-primary hover:bg-layer-hover-01 disabled:cursor-not-allowed disabled:text-icon-disabled",
        className,
    )}
    children={children || Fallback}
    {...restProps}
/>
