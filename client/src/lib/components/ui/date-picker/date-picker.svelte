<script lang="ts">
    import { Calendar } from "$lib/components/ui/calendar/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { parseDate, type DateValue } from "@internationalized/date";
    import CalendarIcon from "carbon-icons-svelte/lib/Calendar.svelte";
    import type { HTMLInputAttributes } from "svelte/elements";

    // Carbon DatePicker, single: a text input typed as yyyy-mm-dd (the stored format); the calendar
    // opens below the field. Values from @carbon/styles 1.117.0 date-picker/_date-picker.scss.
    // Deviations (DESIGN.md): fills its column (Carbon 288 px); body-compact-01, not code-02 mono;
    // a calendar button (48 px, icon where Carbon's sits) instead of opening on input click.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        hideLabel = false,
        value = $bindable(""),
        id = uid,
        ref = $bindable(null),
        class: className,
        ...restProps
    }: Omit<HTMLInputAttributes, "type" | "value" | "files"> & {
        labelText: string;
        hideLabel?: boolean;
        value?: string;
        id?: string;
        ref?: HTMLInputElement | null;
        class?: string;
    } = $props();

    let open = $state(false);
    let field = $state<HTMLElement | null>(null);
    let calendar = $state<HTMLElement | null>(null);
    // Checked when the field changes (blur), not on every key.
    let checked = $state(false);
    const date = $derived(toDate(value));
    const showInvalid = $derived(checked && value !== "" && !date);
    const errorId = $derived(`${id}-error`);

    function toDate(text: string): DateValue | undefined {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return undefined;
        try {
            return parseDate(text);
        } catch {
            return undefined;
        }
    }

    function pick(picked: DateValue | undefined) {
        if (!picked) return;
        value = picked.toString();
        open = false;
    }
</script>

<Field.Field class={className}>
    <Field.Label for={id} class={hideLabel ? "sr-only" : undefined}
        >{labelText}</Field.Label
    >
    <div bind:this={field} class="relative">
        <Input
            {...restProps}
            bind:ref
            bind:value
            {id}
            type="text"
            placeholder="yyyy-mm-dd"
            autocomplete="off"
            aria-invalid={showInvalid || undefined}
            aria-describedby={showInvalid ? errorId : undefined}
            class="pe-12"
            oninput={() => (checked = false)}
            onchange={() => (checked = true)}
        />
        <Popover.Root bind:open>
            <Popover.Trigger>
                {#snippet child({ props })}
                    <button
                        {...props}
                        type="button"
                        aria-label="Choose a date"
                        class="absolute end-0 top-0 flex h-10 w-12 cursor-pointer items-center justify-center text-icon-primary"
                    >
                        <CalendarIcon />
                    </button>
                {/snippet}
            </Popover.Trigger>
            <Popover.Content
                bind:ref={calendar}
                customAnchor={field}
                align="start"
                sideOffset={0}
                onOpenAutoFocus={(e) => {
                    // Focus the selected (or today's) day, which holds the calendar's roving tabindex.
                    e.preventDefault();
                    requestAnimationFrame(() =>
                        calendar
                            ?.querySelector<HTMLElement>(
                                "[data-bits-day][tabindex='0']",
                            )
                            ?.focus(),
                    );
                }}
                class="w-auto rounded-none border-0 bg-transparent p-0 shadow-popover"
            >
                <!-- preventDeselect: clicking the selected day must not clear it (pick ignores undefined). -->
                <Calendar
                    type="single"
                    preventDeselect
                    value={date}
                    onValueChange={pick}
                />
            </Popover.Content>
        </Popover.Root>
    </div>
    {#if showInvalid}
        <Field.Error id={errorId}>Enter a date as yyyy-mm-dd</Field.Error>
    {/if}
</Field.Field>
