<script lang="ts">
    import { Calendar as CalendarPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        ...restProps
    }: CalendarPrimitive.HeaderProps = $props();
</script>

<CalendarPrimitive.Header
    bind:ref
    class={cn("flex h-10 items-center justify-between", className)}
    {...restProps}
/>
