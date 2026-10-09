<script lang="ts">
    import { Calendar as CalendarPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        ...restProps
    }: CalendarPrimitive.CellProps = $props();
</script>

<CalendarPrimitive.Cell
    bind:ref
    class={cn(
        "text-sm [&:first-child[data-selected]_[data-bits-day]]:rounded-l-md [&:last-child[data-selected]_[data-bits-day]]:rounded-r-md relative size-(--cell-size) p-0 text-center focus-within:z-20",
        className,
    )}
    {...restProps}
/>
