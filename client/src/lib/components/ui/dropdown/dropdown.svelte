<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import * as Select from "$lib/components/ui/select/index.js";

    // Carbon Dropdown (carbon-components-svelte prop names) over ui/select, size lg (48 px) or md (40 px).
    // `onselect` fires only when the user picks a different item.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        items,
        selectedId = $bindable(),
        labelText,
        type = "default",
        size = "lg",
        id = uid,
        onselect,
    }: {
        items: { id: string; text: string }[];
        selectedId?: string;
        labelText: string;
        type?: "default" | "inline";
        size?: "md" | "lg";
        id?: string;
        onselect?: (selectedId: string) => void;
    } = $props();

    const selectedText = $derived(
        items.find((i) => i.id === selectedId)?.text ?? "",
    );
</script>

<div
    class={type === "inline"
        ? "flex items-center gap-2"
        : "flex flex-col gap-2"}
>
    <Label
        id="{id}-label"
        for={id}
        class={type === "inline" ? "text-body-compact-01" : undefined}
    >
        {labelText}
    </Label>
    <Select.Root
        type="single"
        items={items.map((i) => ({ value: i.id, label: i.text }))}
        bind:value={
            () => selectedId ?? "",
            (v) => {
                if (v === selectedId) return;
                selectedId = v;
                onselect?.(v);
            }
        }
    >
        <!-- label then trigger, so the name includes the selected value: "Status Not started" -->
        <Select.Trigger
            {id}
            aria-labelledby="{id}-label {id}"
            variant={type}
            class={size === "md" ? "h-10" : undefined}
        >
            {selectedText}
        </Select.Trigger>
        <Select.Content variant={type}>
            {#each items as item (item.id)}
                <Select.Item value={item.id} label={item.text} />
            {/each}
        </Select.Content>
    </Select.Root>
</div>
