<!--
@component
The set's saved status as a read-only Tag beside "Set n of N". A pick that didn't save leaves it as it was.
-->
<script lang="ts">
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { subtasks } from "$lib/data/stores.svelte";
    import type { SubTaskState } from "../../types/openapi_types";
    import { SUBTASK_STATUS } from "./subtaskStatus";

    let { subTaskId }: { subTaskId: number } = $props();

    // ASSUMPTION: tag colours by status, as in the header mockup the user chose.
    const TYPES = {
        NotStarted: "gray",
        Busy: "blue",
        Ready: "green",
    } as const satisfies Record<SubTaskState, string>;
    const state = $derived<SubTaskState>(
        subtasks.get(subTaskId)?.task_state ?? "NotStarted",
    );
</script>

<Tag type={TYPES[state]} icon={SUBTASK_STATUS[state].icon}
    >{SUBTASK_STATUS[state].label}</Tag
>
