<script lang="ts">
    import { Calendar as CalendarPrimitive } from "bits-ui";
    import * as Calendar from "./index.js";
    import { cn, type WithoutChildrenOrChild } from "$lib/utils.js";

    // Carbon DatePicker calendar (its flatpickr theme): 288 px on layer-01, 40 px cells, month and year
    // as a heading (no year input; the date can be typed). Values from @carbon/styles 1.117.0
    // date-picker/_flatpickr.scss.
    let {
        ref = $bindable(null),
        value = $bindable(),
        placeholder = $bindable(),
        class: className,
        weekdayFormat = "short",
        locale = "en-US",
        ...restProps
    }: WithoutChildrenOrChild<CalendarPrimitive.RootProps> = $props();
</script>

<!--
Discriminated Unions + Destructing (required for bindable) do not
get along, so we shut typescript up by casting `value` to `never`.
-->
<CalendarPrimitive.Root
    bind:value={value as never}
    bind:ref
    bind:placeholder
    {weekdayFormat}
    {locale}
    class={cn("w-72 bg-layer-01 px-1 pt-1 pb-2", className)}
    {...restProps}
>
    {#snippet children({ months, weekdays })}
        <Calendar.Header>
            <Calendar.PrevButton />
            <Calendar.Heading />
            <Calendar.NextButton />
        </Calendar.Header>
        {#each months as month (month)}
            <Calendar.Grid>
                <Calendar.GridHead>
                    <Calendar.GridRow>
                        {#each weekdays as weekday (weekday)}
                            <Calendar.HeadCell>
                                {weekday.slice(0, 2)}
                            </Calendar.HeadCell>
                        {/each}
                    </Calendar.GridRow>
                </Calendar.GridHead>
                <Calendar.GridBody>
                    {#each month.weeks as weekDates (weekDates)}
                        <Calendar.GridRow>
                            {#each weekDates as date (date)}
                                <Calendar.Cell {date} month={month.value}>
                                    <Calendar.Day />
                                </Calendar.Cell>
                            {/each}
                        </Calendar.GridRow>
                    {/each}
                </Calendar.GridBody>
            </Calendar.Grid>
        {/each}
    {/snippet}
</CalendarPrimitive.Root>
