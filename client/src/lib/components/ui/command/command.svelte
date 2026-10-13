<script lang="ts">
    import { Command as CommandPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        value = $bindable(""),
        class: className,
        ...restProps
    }: CommandPrimitive.RootProps = $props();
</script>

<CommandPrimitive.Root
    bind:value
    bind:ref
    data-slot="command"
    class={cn(
        "flex h-full w-full flex-col overflow-hidden bg-layer-01 text-text-primary in-dialog:bg-layer-02",
        className,
    )}
    {...restProps}
/>
