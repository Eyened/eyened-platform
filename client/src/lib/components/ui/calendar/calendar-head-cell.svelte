<script lang="ts">
    import { Calendar as CalendarPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        ...restProps
    }: CalendarPrimitive.HeadCellProps = $props();
</script>

<CalendarPrimitive.HeadCell
    bind:ref
    class={cn(
        "flex size-10 items-center justify-center text-body-compact-01 text-text-primary",
        className,
    )}
    {...restProps}
/>
