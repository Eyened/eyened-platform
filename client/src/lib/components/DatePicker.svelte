<script lang="ts">
  import { Button } from "$lib/components/ui/button/index.js";
  import { Calendar } from "$lib/components/ui/calendar/index.js";
  import * as Popover from "$lib/components/ui/popover/index.js";
  import {
      type DateValue,
      DateFormatter,
      getLocalTimeZone,
  } from "@internationalized/date";
  import CalendarIcon from "@lucide/svelte/icons/calendar";
 
  const df = new DateFormatter("en-US", {
    dateStyle: "long",
  });

  let { value = $bindable<DateValue>() } = $props();
</script>
 
<Popover.Root>
  <Popover.Trigger>
    {#snippet child({ props })}
      <Button
        variant="outline"
        class="text-left"
        {...props}
      >
        <div class="flex justify-start items-center">
        <CalendarIcon class="mr-2 size-4" />
        {value ? df.format(value.toDate(getLocalTimeZone())) : "Select a date"}
        </div>
      </Button>
    {/snippet}
  </Popover.Trigger>
  <Popover.Content class="w-auto p-0">
    <Calendar bind:value type="single" captionLayout="dropdown" initialFocus />
  </Popover.Content>
</Popover.Root>