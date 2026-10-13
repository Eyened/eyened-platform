<script lang="ts">
    import { Calendar as CalendarPrimitive } from "bits-ui";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import { cn } from "$lib/utils.js";

    // Carbon .flatpickr-next-month: 40 px, hover layer-hover-01.
    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: CalendarPrimitive.NextButtonProps = $props();
</script>

{#snippet Fallback()}
    <ChevronRight />
{/snippet}

<CalendarPrimitive.NextButton
    bind:ref
    class={cn(
        "flex size-10 cursor-pointer items-center justify-center text-icon-primary hover:bg-layer-hover-01 disabled:cursor-not-allowed disabled:text-icon-disabled",
        className,
    )}
    children={children || Fallback}
    {...restProps}
/>
