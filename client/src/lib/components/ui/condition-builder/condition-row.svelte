<script lang="ts">
    import { DatePicker } from "$lib/components/ui/date-picker/index.js";
    import { NumberInput } from "$lib/components/ui/number-input/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import { cn } from "$lib/utils.js";
    import { mergeProps } from "bits-ui";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import AddAlt from "carbon-icons-svelte/lib/AddAlt.svelte";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import WarningAltFilled from "carbon-icons-svelte/lib/WarningAltFilled.svelte";
    import { onMount } from "svelte";
    import type { Cell } from "./grid-navigation.js";
    import ItemOption from "./item-option.svelte";
    import type { BuilderProperty, BuilderRow } from "./types.js";

    // One ConditionBuilder condition (ConditionBlock): a static "if"/"and", then property, operator
    // and value cells, each a button with its popover, then Delete and, on the last row, Add.
    // Values from @carbon/ibm-products-styles 2.95.0 _conditionBuilderItem.scss (button: 32 px,
    // layer-01, hover layer-hover-01; property in heading-01; value truncated at 10 rem).
    type Part = "property" | "operator" | "value";

    let {
        row,
        index,
        properties,
        cells,
        tabStop,
        openOnMount,
        onchange,
        onremove,
        onadd,
    }: {
        row: BuilderRow;
        index: number;
        properties: BuilderProperty[];
        /** This row's focusable cells (rowCells). */
        cells: Cell[];
        /** The grid's Tab stop, if it is in this row. */
        tabStop: Cell | null;
        /** A new row opens its property popover. */
        openOnMount: boolean;
        onchange: (row: BuilderRow) => void;
        onremove: () => void;
        onadd: () => void;
    } = $props();

    const uid = $props.id();
    const ADD: Record<Part, string> = {
        property: "Add property",
        operator: "Add operator",
        value: "Add value",
    };
    const cellButton =
        "inline-flex h-8 cursor-pointer items-center gap-1 bg-layer-01 px-2 whitespace-nowrap text-text-primary hover:bg-layer-hover-01 in-dialog:bg-layer-02 in-dialog:hover:bg-layer-hover-02";

    const property = $derived(properties.find((p) => p.id === row.property));
    const operator = $derived(
        property?.operators.find((o) => o.id === row.operator),
    );
    const valueText = $derived(
        Array.isArray(row.value) ? row.value.join(", ") : (row.value ?? ""),
    );
    const parts = $derived(
        cells.filter(
            (c): c is Part =>
                c === "property" || c === "operator" || c === "value",
        ),
    );
    // The first missing part; it reads "Incomplete" once closed without a choice.
    const missing = $derived<Part | null>(
        !property
            ? "property"
            : !operator
              ? "operator"
              : operator.value !== "none" && valueText === ""
                ? "value"
                : null,
    );
    const titles = $derived<Record<Part, string>>({
        property: "Property",
        operator: "Operator",
        value: property?.label ?? "Value",
    });

    let openPart = $state<Part | null>(null);
    let chainTo: Part | null = null;
    const triggers: Record<Part, HTMLElement | null> = $state({
        property: null,
        operator: null,
        value: null,
    });
    const contents: Record<Part, HTMLElement | null> = $state({
        property: null,
        operator: null,
        value: null,
    });

    onMount(() => {
        if (openOnMount) openPart = "property";
    });

    function text(part: Part): string {
        if (part === "property") return property?.label ?? "";
        if (part === "operator") return operator?.label ?? "";
        return valueText;
    }

    // bits-ui closes on Escape and outside clicks. A part closed without a choice is Incomplete.
    function setOpen(part: Part, open: boolean) {
        if (open) {
            openPart = part;
            return;
        }
        if (openPart !== part) return;
        openPart = null;
        if (text(part) === "") onchange({ ...row, incomplete: true });
    }

    // A choice closes its part; once that popover is gone, the next part opens.
    function closeThen(next: Part | null) {
        chainTo = next;
        openPart = null;
    }

    // bits-ui would return focus to whatever was focused before the popover opened, which after a
    // chained open is nothing. Send it to this part's cell, or open the next part.
    function onCloseAutoFocus(e: Event, part: Part) {
        e.preventDefault();
        if (chainTo) {
            openPart = chainTo;
            chainTo = null;
            return;
        }
        triggers[part]?.focus();
    }

    // Focus the search or value field, else the list; not the popover. (One selector would return
    // the Command root, which comes before its search field in document order.)
    function onOpenAutoFocus(e: Event, part: Part) {
        e.preventDefault();
        requestAnimationFrame(() => {
            const content = contents[part];
            (
                content?.querySelector<HTMLElement>("input") ??
                content?.querySelector<HTMLElement>("[data-slot='command']")
            )?.focus();
        });
    }

    function pickProperty(id: string) {
        onchange({ id: row.id, property: id });
        closeThen("operator");
    }

    function pickOperator(id: string) {
        const next = property?.operators.find((o) => o.id === id);
        onchange({
            id: row.id,
            property: row.property,
            operator: id,
            value: next?.value === "list" ? [] : "",
        });
        closeThen(next && next.value !== "none" ? "value" : null);
    }

    function toggleValue(id: string) {
        const current = Array.isArray(row.value) ? row.value : [];
        onchange({
            ...row,
            value: current.includes(id)
                ? current.filter((v) => v !== id)
                : [...current, id],
            incomplete: false,
        });
    }

    function setValue(value: string) {
        onchange({ ...row, value, incomplete: false });
    }

    // Text, number and date popovers commit on Enter.
    function commitOnEnter(e: KeyboardEvent) {
        if (e.key !== "Enter") return;
        e.preventDefault();
        setOpen("value", false);
    }
</script>

{#snippet partCell(part: Part)}
    {@const label = text(part)}
    {@const incomplete = !!row.incomplete && missing === part}
    {@const tip =
        label === "" && !incomplete ? ADD[part] : part === "value" ? label : ""}
    <span role="gridcell">
        <Popover.Root
            bind:open={() => openPart === part, (open) => setOpen(part, open)}
        >
            <Popover.Trigger>
                {#snippet child({ props: popoverProps })}
                    <Tooltip.Root disabled={tip === ""}>
                        <Tooltip.Trigger>
                            {#snippet child({ props: tooltipProps })}
                                <button
                                    {...mergeProps(popoverProps, tooltipProps)}
                                    bind:this={triggers[part]}
                                    type="button"
                                    data-row={index}
                                    data-cell={part}
                                    tabindex={tabStop === part ? 0 : -1}
                                    aria-label={incomplete
                                        ? `Incomplete: ${titles[part]} — Condition ${index + 1}`
                                        : label === ""
                                          ? ADD[part]
                                          : undefined}
                                    class={cn(
                                        cellButton,
                                        part === "property" &&
                                            "text-heading-compact-01",
                                        part === "value" && "max-w-40",
                                    )}
                                >
                                    {#if incomplete}
                                        <WarningAltFilled
                                            aria-hidden="true"
                                            class="text-support-warning"
                                        />
                                        Incomplete
                                    {:else if label === ""}
                                        <Add aria-hidden="true" />
                                    {:else}
                                        <span class="truncate">{label}</span>
                                    {/if}
                                </button>
                            {/snippet}
                        </Tooltip.Trigger>
                        {#if tip}
                            <Tooltip.Content size="icon">{tip}</Tooltip.Content>
                        {/if}
                    </Tooltip.Root>
                {/snippet}
            </Popover.Trigger>
            <Popover.Content
                bind:ref={contents[part]}
                data-slot="condition-popover"
                align="start"
                sideOffset={0}
                aria-label="{titles[part]} — Condition {index + 1}"
                onOpenAutoFocus={(e) => onOpenAutoFocus(e, part)}
                onCloseAutoFocus={(e) => onCloseAutoFocus(e, part)}
                class="max-h-88 w-auto max-w-80 min-w-48 overflow-auto rounded-none border-0 bg-layer-01 p-0 text-text-primary shadow-popover"
            >
                <h3 class="p-4 text-heading-compact-01">{titles[part]}</h3>
                {#if part === "property"}
                    <ItemOption
                        options={properties}
                        selected={row.property ? [row.property] : []}
                        label="Property"
                        onselect={pickProperty}
                    />
                {:else if part === "operator"}
                    <ItemOption
                        options={property?.operators ?? []}
                        selected={row.operator ? [row.operator] : []}
                        label="Operator"
                        onselect={pickOperator}
                    />
                {:else if operator?.value === "list"}
                    <ItemOption
                        multi
                        options={(property?.options ?? []).map((v) => ({
                            id: v,
                            label: v,
                        }))}
                        selected={Array.isArray(row.value) ? row.value : []}
                        label={titles.value}
                        searchLabel="Search values"
                        onselect={toggleValue}
                    />
                {:else}
                    <div class="px-4 pb-4">
                        {#if operator?.value === "number"}
                            <NumberInput
                                hideLabel
                                labelText={titles.value}
                                bind:value={() => valueText, setValue}
                                onkeydown={commitOnEnter}
                            />
                        {:else if operator?.value === "date"}
                            <DatePicker
                                hideLabel
                                labelText={titles.value}
                                bind:value={() => valueText, setValue}
                                onkeydown={commitOnEnter}
                            />
                        {:else}
                            <TextInput
                                hideLabel
                                labelText={titles.value}
                                bind:value={() => valueText, setValue}
                                onkeydown={commitOnEnter}
                                aria-describedby={operator?.helperText
                                    ? `${uid}-help`
                                    : undefined}
                            />
                            {#if operator?.helperText}
                                <p
                                    id="{uid}-help"
                                    class="mt-2 text-helper-text-01 text-text-helper"
                                >
                                    {operator.helperText}
                                </p>
                            {/if}
                        {/if}
                    </div>
                {/if}
            </Popover.Content>
        </Popover.Root>
    </span>
{/snippet}

{#snippet iconCell(cell: "delete" | "add", label: string, onclick: () => void)}
    <!-- ConditionBlock / ConditionBuilderAdd: gridcells "Delete condition" and "Add condition row". -->
    <span
        role="gridcell"
        aria-label={cell === "add" ? "Add condition row" : "Delete condition"}
        class={cell === "add" ? "ms-0.5" : undefined}
    >
        <Tooltip.Root>
            <Tooltip.Trigger>
                {#snippet child({ props })}
                    <button
                        {...mergeProps(props, { onclick })}
                        type="button"
                        aria-label={label}
                        data-row={index}
                        data-cell={cell}
                        tabindex={tabStop === cell ? 0 : -1}
                        class={cellButton}
                    >
                        {#if cell === "add"}
                            <AddAlt aria-hidden="true" />
                        {:else}
                            <Close aria-hidden="true" />
                        {/if}
                    </button>
                {/snippet}
            </Tooltip.Trigger>
            <Tooltip.Content size="icon">{label}</Tooltip.Content>
        </Tooltip.Root>
    </span>
{/snippet}

<!-- Only the part cells wrap; Delete and Add stay on the first line. -->
<div
    role="row"
    aria-label="Condition row"
    class="mb-0.5 flex basis-full items-start"
>
    <!-- Static connector (__connector--disabled): the server ANDs every condition. -->
    <span
        role="gridcell"
        class="me-0.5 flex h-8 min-w-16 shrink-0 items-center bg-layer-01 px-2 text-text-helper in-dialog:bg-layer-02"
    >
        {index === 0 ? "if" : "and"}
    </span>
    <div class="flex min-w-0 flex-1 flex-wrap gap-y-0.5">
        {#each parts as part (part)}
            {@render partCell(part)}
        {/each}
    </div>
    {@render iconCell("delete", "Delete condition", onremove)}
    {#if cells.includes("add")}
        {@render iconCell("add", "Add condition", onadd)}
    {/if}
</div>
