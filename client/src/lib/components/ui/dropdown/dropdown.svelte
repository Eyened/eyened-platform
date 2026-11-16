<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import * as Select from "$lib/components/ui/select/index.js";

    // Carbon Dropdown (carbon-components-svelte prop names) over ui/select, size lg (48 px), md (40 px) or sm (32 px);
    // menu items match the field height and the menu shows 5.5 items (@carbon/styles 1.117.0 list-box).
    // An item's optional `hint` (a shortcut key) follows its text in the menu.
    // An item's optional `thumb` (an image URL) shows as a 24 px square before its text, also in the closed field; `description` follows the text in the menu.
    // `onselect` fires only when the user picks a different item; the optional `onclose` fires whenever the menu closes.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        items,
        selectedId = $bindable(),
        labelText,
        type = "default",
        size = "lg",
        hideLabel = false,
        direction = "bottom",
        id = uid,
        onselect,
        onclose,
    }: {
        items: {
            id: string;
            text: string;
            hint?: string;
            thumb?: string;
            description?: string;
        }[];
        selectedId?: string;
        labelText: string;
        type?: "default" | "inline";
        size?: "sm" | "md" | "lg";
        hideLabel?: boolean;
        direction?: "top" | "bottom";
        id?: string;
        onselect?: (selectedId: string) => void;
        onclose?: () => void;
    } = $props();

    const heights = { sm: "h-8", md: "h-10", lg: undefined };
    const selected = $derived(items.find((i) => i.id === selectedId));
    const selectedText = $derived(selected?.text ?? "");
</script>

<div
    class={type === "inline"
        ? "flex items-center gap-2"
        : "flex flex-col gap-2"}
>
    <Label
        id="{id}-label"
        for={id}
        class={hideLabel
            ? "sr-only"
            : type === "inline"
              ? "text-body-compact-01"
              : undefined}
    >
        {labelText}
    </Label>
    <Select.Root
        type="single"
        onOpenChange={(open) => {
            if (!open) onclose?.();
        }}
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
            class={heights[size]}
        >
            {#if selected?.thumb}
                <img
                    src={selected.thumb}
                    alt=""
                    class="size-6 shrink-0 object-cover"
                />
            {/if}
            {selectedText}
        </Select.Trigger>
        <Select.Content
            variant={type}
            side={direction}
            class={size === "md"
                ? "max-h-55"
                : size === "sm"
                  ? "max-h-44"
                  : undefined}
        >
            {#each items as item (item.id)}
                <Select.Item
                    value={item.id}
                    label={item.text}
                    class={heights[size]}
                >
                    <!-- No whitespace before the text, so the option's text starts with it. -->
                    <!-- prettier-ignore -->
                    {#if item.thumb}<img src={item.thumb} alt="" class="me-2 size-6 shrink-0 object-cover" />{/if}{item.text}
                    {#if item.description}
                        <span class="ms-2 text-text-secondary"
                            >{item.description}</span
                        >
                    {/if}
                    {#if item.hint}
                        <span class="ms-2 text-text-secondary">{item.hint}</span
                        >
                    {/if}
                </Select.Item>
            {/each}
        </Select.Content>
    </Select.Root>
</div>
