<script lang="ts" generics="T extends string">
    import { cn } from "$lib/utils.js";
    import RadioButton from "./radio-button.svelte";

    // Carbon radio button group: a label-01 legend 8 px above the items, 8 px between items.
    let {
        legendText,
        items,
        selected = $bindable(),
        disabled = false,
        describedBy,
        class: className,
    }: {
        legendText: string;
        items: readonly { value: T; labelText: string }[];
        selected: T;
        disabled?: boolean;
        /** Id of helper text for the whole group. */
        describedBy?: string;
        class?: string;
    } = $props();

    const name = $props.id();
</script>

<!-- A disabled fieldset disables every radio in it, so Tab skips them; the helper says why. -->
<fieldset
    class={cn("group/radios flex min-w-0 flex-col", className)}
    {disabled}
    aria-describedby={describedBy}
>
    <legend
        class="mb-2 text-label-01 text-text-secondary group-disabled/radios:text-text-disabled"
        >{legendText}</legend
    >
    <div class="flex flex-wrap gap-2">
        {#each items as item (item.value)}
            <RadioButton
                {name}
                value={item.value}
                labelText={item.labelText}
                checked={selected === item.value}
                onchange={() => (selected = item.value)}
            />
        {/each}
    </div>
</fieldset>
