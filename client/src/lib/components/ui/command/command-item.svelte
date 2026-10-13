<script lang="ts">
    import { Command as CommandPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        ...restProps
    }: CommandPrimitive.ItemProps = $props();
</script>

<CommandPrimitive.Item
    bind:ref
    data-slot="command-item"
    class={cn(
        // ConditionBuilder option (_conditionBuilderItem.scss .item-option__option): 32 px minimum, hover
        // layer-hover; bits-ui's highlighted option (data-selected) gets the focus outline; a chosen
        // option (aria-checked) is layer-selected.
        "relative flex min-h-8 cursor-pointer items-center gap-2 px-4 text-body-01 text-text-primary select-none hover:bg-layer-hover-01 aria-checked:bg-layer-selected-01 aria-checked:hover:bg-layer-selected-hover-01 data-disabled:cursor-not-allowed data-disabled:text-text-disabled data-selected:outline-2 data-selected:-outline-offset-2 data-selected:outline-focus in-dialog:hover:bg-layer-hover-02 in-dialog:aria-checked:bg-layer-selected-02 in-dialog:aria-checked:hover:bg-layer-selected-hover-02 [&_svg]:pointer-events-none [&_svg]:shrink-0",
        className,
    )}
    {...restProps}
/>
