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
    - The search parameters 'StudyDate', 'StudyDate~~gte', and 'StudyDate~~lte' are used to represent the selected dates.
-->

<script lang="ts">
    import { removeParam, setParam } from "./browserContext.svelte";
    import { getParam } from "./browserContext.svelte";
    let date: string = $state(getParam("StudyDate") ?? "");
    let startDate: string = $state(getParam("StudyDate~~gte") ?? "");
    let endDate: string = $state(getParam("StudyDate~~lte") ?? "");

    function setDates() {
        if (date) {
            setParam("StudyDate", date);
        } else {
            removeParam("StudyDate", date);
        }
        if (startDate) {
            setParam("StudyDate~~gte", startDate);
        } else {
            removeParam("StudyDate~~gte", startDate);
        }
        if (endDate) {
            setParam("StudyDate~~lte", endDate);
        } else {
            removeParam("StudyDate~~lte", endDate);
        }
    }
</script>

<div>
    Date: <input
        type="date"
        bind:value={date}
        oninput={setDates}
    />
</div>
<div>
    From: <input
        type="date"
        bind:value={startDate}
        oninput={setDates}
    />
    To:
    <input
        type="date"
        bind:value={endDate}
        oninput={setDates}
    />
</div>
