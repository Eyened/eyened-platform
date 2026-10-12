<script lang="ts">
    import Main from "$lib/components/Main.svelte";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { fetchTasks } from "$lib/data/api";
    import TasksTable from "$lib/tasks/TasksTable.svelte";

    const headingId = "tasks-heading";
    const loading = fetchTasks();
</script>

<Main>
    <!-- tabindex=-1: focus lands here after a delete -->
    <h1
        id={headingId}
        tabindex="-1"
        class="mt-8 mb-6 text-heading-04 text-text-primary"
    >
        Tasks
    </h1>
    {#await loading then list}
        <TasksTable rows={list} {headingId} />
    {:catch error}
        <InlineNotification
            title="Tasks could not be loaded"
            subtitle={error instanceof Error ? error.message : String(error)}
        />
    {/await}
</Main>
