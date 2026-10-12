<script lang="ts">
    import { Progress as ProgressPrimitive } from "bits-ui";
    import { cn, type WithoutChildrenOrChild } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        max = 100,
        value,
        ...restProps
    }: WithoutChildrenOrChild<ProgressPrimitive.RootProps> = $props();
</script>

<ProgressPrimitive.Root
    bind:ref
    data-slot="progress"
    class={cn(
        "relative h-2 w-full min-w-12 overflow-hidden bg-border-subtle-00",
        className,
    )}
    {value}
    {max}
    {...restProps}
>
    <div
        data-slot="progress-indicator"
        class="h-full w-full bg-interactive transition-transform duration-110"
        style="transform: translateX(-{100 -
            (100 * (value ?? 0)) / (max ?? 1)}%)"
    ></div>
</ProgressPrimitive.Root>
