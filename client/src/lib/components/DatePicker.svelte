<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Calendar } from "$lib/components/ui/calendar/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import {
        type DateValue,
        DateFormatter,
        getLocalTimeZone,
        parseDate,
    } from "@internationalized/date";
    import CalendarIcon from "@lucide/svelte/icons/calendar";

    const df = new DateFormatter("en-US", {
        dateStyle: "long",
    });

    // External string prop (bindable)
    let {
        value = $bindable<string>(""),
        onchange,
    }: { value?: string; onchange?: (v: string) => void } = $props();

    function fromString(s: string): DateValue | undefined {
        if (!s) return undefined;
        try {
            return parseDate(s);
        } catch {
            return undefined;
        }
    }

    function toStringDate(d?: DateValue): string {
        return d ? d.toString() : "";
    }

    // Internal calendar value, derived from the external string prop.
    // Reassigned directly by bind:value / onCalendarChange (writable derived).
    let internalDate: DateValue | undefined = $derived(fromString(value));

    function onCalendarChange(d?: DateValue) {
        internalDate = d;
        const s = toStringDate(d);
        value = s;
        onchange?.(s);
    }
</script>

<Popover.Root>
    <Popover.Trigger>
        {#snippet child({ props })}
            <Button variant="outline" class="text-left" {...props}>
                <div class="flex items-center justify-start">
                    <CalendarIcon class="mr-2 size-4" />
                    {internalDate
                        ? df.format(internalDate.toDate(getLocalTimeZone()))
                        : "Select a date"}
                </div>
            </Button>
        {/snippet}
    </Popover.Trigger>
    <Popover.Content class="w-auto p-0">
        <Calendar
            bind:value={internalDate}
            type="single"
            captionLayout="dropdown"
            initialFocus
            onValueChange={onCalendarChange}
        />
    </Popover.Content>
</Popover.Root>
