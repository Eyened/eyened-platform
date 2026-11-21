<!--
@component
"Edit with" and a tertiary button that arms the tool that changes this pane's item. Panes show it where they show Delete.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { toolById, type ToolId } from "$lib/workspace/tools/registry";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getContext } from "svelte";

    let { tool: id }: { tool: ToolId } = $props();
    const workspace = getContext<Workspace>("workspace");
    const uid = $props.id();
    const tool = $derived(toolById(id));
</script>

<div
    role="group"
    aria-labelledby="{uid}-label"
    class="flex flex-none flex-col items-start gap-2 px-4 py-3"
>
    <span id="{uid}-label" class="text-label-01 text-text-secondary"
        >Edit with</span
    >
    <Button
        variant="outline"
        size="sm"
        aria-keyshortcuts={tool.key ?? undefined}
        onclick={() => workspace.arm(id)}
        >{tool.name}{#if tool.key}<kbd aria-hidden="true" class="font-sans"
                >{tool.key}</kbd
            >{/if}<tool.icon /></Button
    >
</div>
