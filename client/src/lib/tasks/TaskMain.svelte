<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import ViewerWindowLoader from "$lib/viewer-window/ViewerWindowLoader.svelte";
    import { getContext, setContext } from "svelte";

    const taskContext: TaskContext = $props();
    setContext("taskContext", taskContext);
    const globalContext = getContext<GlobalContext>("globalContext");

    globalContext.updateConfig(taskContext.task.task_definition.config);

    const instanceIDs = taskContext.subTask.images.map(image => image.id);
</script>

<ViewerWindowLoader {instanceIDs} />
