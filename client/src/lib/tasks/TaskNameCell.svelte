<script lang="ts">
    import * as Tooltip from "$lib/components/ui/tooltip";
    import type { TaskGET } from "../../types/openapi_types";

    let { task, url }: { task: TaskGET; url: string } = $props();
</script>

<Tooltip.Root>
    <Tooltip.Trigger>
        <a href={url} class="text-blue-600 underline hover:no-underline">
            {task.name}
        </a>
    </Tooltip.Trigger>
    <Tooltip.Content sideOffset={6}>
        <div class="p-2 text-sm">
            {task.description || "No description"}
        </div>
    </Tooltip.Content>
</Tooltip.Root>
