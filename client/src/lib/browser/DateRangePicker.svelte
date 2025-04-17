<!--
  DateRangePicker.svelte

  This component allows users to select a single date or a date range.
  It updates the URL search parameters based on the selected dates.

  Props:
    - None

  State:
    - date: string - The selected single date.
    - startDate: string - The start date of the selected date range.
    - endDate: string - The end date of the selected date range.

  Behavior:
    - When any of the date inputs change, the URL search parameters are updated.
    - The search parameters 'StudyDate', 'StudyDate~~>=', and 'StudyDate~~<=' are used to represent the selected dates.
-->

<script lang="ts">
    import { browser } from "$app/environment";
    import { page } from "$app/state";

    let date: string = $state();
    let startDate: string = $state();
    let endDate: string = $state();

    $effect(() => {
        if (!browser) {
            return;
        }
        if (date || startDate || endDate) {
            const params = page.url.searchParams;

            params.delete("StudyDate");
            params.delete("StudyDate~~>=");
            params.delete("StudyDate~~<=");

            if (date) params.append("StudyDate", date);
            if (startDate) params.append("StudyDate~~>=", startDate);
            if (endDate) params.append("StudyDate~~<=", endDate);
        }
    });
</script>

<div>Date: <input type="date" bind:value={date} /></div>
<div>
    From: <input type="date" bind:value={startDate} />
    To: <input type="date" bind:value={endDate} />
</div>
