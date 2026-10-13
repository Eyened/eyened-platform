<script lang="ts">
    import { cn } from "$lib/utils.js";
    import { Calendar as CalendarPrimitive } from "bits-ui";

    let {
        ref = $bindable(null),
        class: className,
        ...restProps
    }: CalendarPrimitive.DayProps = $props();
</script>

<!-- Carbon .flatpickr-day: 40 px; today in link-primary at 600 with a 4 px dot; selected button-primary.
     The focus ring colours are unlayered rules in app.css (data-slot="calendar-day"). -->
<CalendarPrimitive.Day
    bind:ref
    data-slot="calendar-day"
    class={cn(
        "relative flex size-10 cursor-pointer items-center justify-center text-body-compact-01 text-text-primary select-none hover:bg-layer-hover-01",
        "data-outside-month:text-text-helper",
        "data-today:text-heading-compact-01 data-today:not-data-selected:text-link-primary data-today:after:absolute data-today:after:bottom-1.75 data-today:after:left-1/2 data-today:after:size-1 data-today:after:-translate-x-1/2 data-today:after:bg-link-primary",
        "data-selected:bg-button-primary data-selected:text-text-on-color data-selected:after:hidden",
        "data-disabled:cursor-not-allowed data-disabled:text-text-disabled data-unavailable:text-text-disabled data-unavailable:line-through",
        className,
    )}
    {...restProps}
/>
