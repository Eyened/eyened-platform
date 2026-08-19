<script lang="ts">
    import type { ResolvedPathname } from "$app/types";
    import * as Tooltip from "$lib/components/ui/tooltip";
    import type { TaskGET } from "../../types/openapi_types";

    let { task, url }: { task: TaskGET; url: ResolvedPathname } = $props();
</script>

<Tooltip.Root>
    <Tooltip.Trigger>
        <!-- eslint-disable svelte/no-navigation-without-resolve -- url is a pre-resolved path supplied by the caller (see TasksTable.svelte, built via resolve()); the prop crosses a component boundary so static analysis can't trace it -->
        <a href={url} class="text-blue-600 underline hover:no-underline">
            {task.name}
        </a>
        <!-- eslint-enable svelte/no-navigation-without-resolve -->
    </Tooltip.Trigger>
    <Tooltip.Content sideOffset={6}>
        <div class="p-2 text-sm">
            {task.description || "No description"}
        </div>
    </Tooltip.Content>
</Tooltip.Root>
