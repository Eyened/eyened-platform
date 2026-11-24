<!--
@component
Carbon combo button, sm: the main action, then ▾ with a single-select menu whose items carry a second line. Two Tab stops.
Without a label only a ghost ▾ is left, showing the selected item. Other attributes go on the main action.
-->
<script lang="ts">
    import {
        Button,
        type ButtonProps,
    } from "$lib/components/ui/button/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { cn } from "$lib/utils.js";
    import { DropdownMenu } from "bits-ui";
    import Checkmark from "carbon-icons-svelte/lib/Checkmark.svelte";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";

    let {
        label,
        onclick,
        pending = false,
        triggerId,
        triggerLabel,
        heading,
        items,
        selectedId,
        onselect,
        menuDisabled = false,
        invalid = false,
        describedBy,
        fullWidth = false,
        action,
        ...mainProps
    }: Omit<
        ButtonProps,
        "onclick" | "onselect" | "href" | "size" | "variant"
    > & {
        /** The main action; without one only a ghost ▾ is left. */
        label?: string;
        onclick?: () => void;
        /** The main action is running: a spinner, and aria-disabled so focus stays on it. */
        pending?: boolean;
        triggerId?: string;
        /** ▾'s accessible name. */
        triggerLabel: string;
        /** The menu's group heading. */
        heading: string;
        items: { id: string; label: string; description: string }[];
        selectedId: string;
        /** Fires only for an item other than the selected one. */
        onselect: (id: string) => void;
        /** ▾ stays focusable but opens nothing. */
        menuDisabled?: boolean;
        /** A red outline; `describedBy` names the text that says why. */
        invalid?: boolean;
        describedBy?: string;
        /** Fills its container, as in the narrow footer; the main part takes the room and its label wraps. */
        fullWidth?: boolean;
        /** One action after the status group, under a divider (Carbon Menu mixes select and non-select items). */
        action?: { label: string; description: string; onselect: () => void };
    } = $props();

    let open = $state(false);
    const itemClass =
        "flex cursor-pointer items-start gap-2 px-4 py-2 text-body-compact-01 text-text-secondary outline-none select-none hover:bg-layer-hover-01 hover:text-text-primary data-highlighted:bg-layer-hover-01 data-highlighted:text-text-primary data-highlighted:outline-2 data-highlighted:-outline-offset-2 data-highlighted:outline-focus";
    const selectedLabel = $derived(
        items.find((i) => i.id === selectedId)?.label ?? "",
    );
</script>

<!-- @carbon/styles 1.117.0 combo-button: the two parts 1 px apart. -->
<!-- The invalid border is an overlay: the buttons are positioned and would paint over the wrapper's own outline. -->
<div
    class={cn(
        "relative gap-px",
        fullWidth ? "flex w-full" : "inline-flex",
        invalid &&
            "after:pointer-events-none after:absolute after:inset-0 after:border-2 after:border-support-error",
    )}
>
    {#if label}
        <Button
            {...mainProps}
            size="sm"
            class={fullWidth
                ? "max-w-none min-w-0 flex-1"
                : "max-w-59.75 min-w-31.75"}
            aria-disabled={pending || undefined}
            onclick={() => onclick?.()}
        >
            {#if pending}
                <InlineLoading
                    class="text-inherit"
                    status="active"
                    description={label}
                    live={false}
                />
            {:else}
                <span class={fullWidth ? "min-w-0 break-words" : "truncate"}
                    >{label}</span
                >
            {/if}
        </Button>
    {/if}
    <DropdownMenu.Root
        bind:open={() => open, (next) => (open = next && !menuDisabled)}
    >
        <DropdownMenu.Trigger id={triggerId}>
            {#snippet child({ props })}
                <Button
                    {...props}
                    variant={label ? "default" : "ghost"}
                    size="sm"
                    aria-label={triggerLabel}
                    aria-disabled={menuDisabled || undefined}
                    aria-describedby={invalid ? describedBy : undefined}
                    class={cn(
                        "[&>svg]:transition-transform data-[state=open]:[&>svg]:rotate-180",
                        label && "w-8 justify-center px-0 [&>svg]:static",
                        // Two lines tall: ▾ stays at the top, level with the first line.
                        label && fullWidth && "items-start [&>svg]:mt-px",
                    )}
                >
                    {#if !label}{selectedLabel}{/if}
                    <ChevronDown aria-hidden="true" />
                </Button>
            {/snippet}
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
            <DropdownMenu.Content
                align="end"
                sideOffset={0}
                class="z-50 w-72 bg-layer-01 py-1 shadow-popover outline-none"
            >
                <DropdownMenu.RadioGroup
                    bind:value={
                        () => selectedId,
                        (id) => {
                            if (id !== selectedId) onselect(id);
                        }
                    }
                >
                    <DropdownMenu.GroupHeading
                        class="flex h-8 items-center px-4 text-label-01 text-text-secondary"
                        >{heading}</DropdownMenu.GroupHeading
                    >
                    {#each items as item (item.id)}
                        <DropdownMenu.RadioItem
                            value={item.id}
                            textValue={item.label}
                            class={itemClass}
                        >
                            {#snippet children({ checked })}
                                <!-- Carbon Menu, single-select: the checkmark in front of the item. -->
                                <span class="flex size-4 shrink-0 items-center">
                                    {#if checked}<Checkmark
                                            aria-hidden="true"
                                        />{/if}
                                </span>
                                <span class="flex min-w-0 flex-col gap-0.5">
                                    <span>{item.label}</span>
                                    <span class="text-helper-text-01"
                                        >{item.description}</span
                                    >
                                </span>
                            {/snippet}
                        </DropdownMenu.RadioItem>
                    {/each}
                </DropdownMenu.RadioGroup>
                {#if action}
                    <DropdownMenu.Separator
                        class="my-1 h-px bg-border-subtle-01"
                    />
                    <DropdownMenu.Item
                        textValue={action.label}
                        onSelect={action.onselect}
                        class={itemClass}
                    >
                        <!-- Lines up with the status labels, after their checkmark column. -->
                        <span class="size-4 shrink-0"></span>
                        <span class="flex min-w-0 flex-col gap-0.5">
                            <span>{action.label}</span>
                            <span class="text-helper-text-01"
                                >{action.description}</span
                            >
                        </span>
                    </DropdownMenu.Item>
                {/if}
            </DropdownMenu.Content>
        </DropdownMenu.Portal>
    </DropdownMenu.Root>
</div>
