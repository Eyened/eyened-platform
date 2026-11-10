<!--
@component
The tool palette: one toolbar, flat while every slot fits, else one slot per job with a list of its tools. Outside All tools, ⋯ More tools holds the rest.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import OverflowMenuHorizontal from "carbon-icons-svelte/lib/OverflowMenuHorizontal.svelte";
    import { getContext } from "svelte";
    import OverflowMenu from "../OverflowMenu.svelte";
    import { rovingIndex } from "../rovingIndex";
    import type { Workspace } from "../workspace.svelte";
    import { paletteLayout, paletteSections } from "./paletteLayout";
    import {
        GROUPS,
        offered,
        TOOLS,
        type ToolDef,
        type ToolGroup,
    } from "./registry";
    import ToolSlot from "./ToolSlot.svelte";

    let {
        available,
        orientation = "vertical",
    }: {
        /** Rail height left for the palette, in px. */
        available: number;
        /** Horizontal in the narrow menu, which is always flat. */
        orientation?: "vertical" | "horizontal";
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const sections = $derived(paletteSections(workspace.toolMode));
    const flat = $derived(
        orientation === "horizontal" ||
            paletteLayout(available, sections) === "flat",
    );
    const leftOut = $derived(
        TOOLS.filter((t) => !offered(t.id, workspace.toolMode)),
    );
    const armedOut = $derived(
        leftOut.find((t) => t.id === workspace.armedTool) ?? null,
    );
    const modal = (tools: ToolDef[]) => tools.filter((t) => t.kind === "modal");
    const actions = (tools: ToolDef[]) =>
        tools.filter((t) => t.kind === "action");

    /** A job's slot shows its armed tool, else its last pick, else its first tool. */
    function shown(group: ToolGroup, tools: ToolDef[]): ToolDef {
        return (
            tools.find((t) => t.id === workspace.armedTool) ??
            tools.find((t) => t.id === workspace.lastPick[group]) ??
            tools[0]
        );
    }

    /** One Tab stop; arrow keys move between slots in markup order. */
    const stops = $derived(
        sections.flatMap((s) => {
            if (s.group === "More") return ["more"];
            const m = modal(s.tools);
            const slots =
                !flat && m.length > 1
                    ? [s.group, `${s.group}-list`]
                    : m.map((t) => t.id);
            return [...slots, ...actions(s.tools).map((t) => t.id)];
        }),
    );
    let current = $state("");
    const active = $derived(stops.includes(current) ? current : stops[0]);
    let toolbar: HTMLElement | undefined = $state();

    function focusStop(key: string) {
        const el = toolbar?.querySelector<HTMLElement>(`[data-stop="${key}"]`);
        (el?.matches("button") ? el : el?.querySelector("button"))?.focus();
    }

    function onkeydown(e: KeyboardEvent) {
        if ((e.target as Element).closest('[data-slot="overflow-menu"]'))
            return;
        const keys =
            orientation === "vertical"
                ? { prev: ["ArrowUp"], next: ["ArrowDown"] }
                : { prev: ["ArrowLeft"], next: ["ArrowRight"] };
        const next = rovingIndex(
            e.key,
            stops.indexOf(active),
            stops.length,
            keys,
        );
        if (next === null) return;
        e.preventDefault();
        current = stops[next];
        focusStop(current);
    }

    function onfocusin(e: FocusEvent) {
        const target = e.target as Element;
        if (target.closest('[data-slot="overflow-menu"]')) return;
        const key = target.closest<HTMLElement>("[data-stop]")?.dataset.stop;
        if (key) current = key;
    }

    const tab = (key: string) => (key === active ? 0 : -1);
</script>

{#snippet toolButton(tool: ToolDef)}
    <IconButton
        label={tool.name}
        shortcut={tool.key ?? undefined}
        aria-keyshortcuts={tool.key === "Esc"
            ? "Escape"
            : (tool.key ?? undefined)}
        aria-pressed={tool.kind === "modal"
            ? workspace.armedTool === tool.id
            : undefined}
        class="aria-pressed:bg-background-selected"
        data-stop={tool.id}
        tabindex={tab(tool.id)}
        onclick={() => workspace.toggleTool(tool.id)}
    >
        <tool.icon />
    </IconButton>
{/snippet}

{#snippet menuRow(tool: ToolDef, close: () => void)}
    <Button
        variant="ghost"
        size="sm"
        class="w-full justify-between gap-8 pe-4"
        aria-keyshortcuts={tool.key ?? undefined}
        aria-pressed={workspace.armedTool === tool.id}
        onclick={() => {
            workspace.arm(tool.id);
            close();
        }}
    >
        {tool.name}
        {#if tool.key}<kbd class="font-sans text-text-secondary">{tool.key}</kbd
            >{/if}
    </Button>
{/snippet}

<!-- svelte-ignore a11y_interactive_supports_focus -->
<div
    bind:this={toolbar}
    role="toolbar"
    aria-label="Tools"
    aria-orientation={orientation}
    class={orientation === "vertical"
        ? "flex flex-col items-center gap-3"
        : "flex flex-wrap gap-3 px-4 py-2"}
    {onkeydown}
    {onfocusin}
>
    {#each sections as section (section.group)}
        <div class={orientation === "vertical" ? "flex flex-col" : "flex"}>
            {#if section.group === "More"}
                <OverflowMenu
                    label={armedOut
                        ? `${armedOut.name} (More tools)`
                        : "More tools"}
                    side={orientation === "vertical" ? "end" : "bottom"}
                    active={armedOut !== null}
                    stop="more"
                    tabindex={tab("more")}
                >
                    {#snippet icon()}
                        {#if armedOut}
                            <armedOut.icon />
                            <span class="flyout-mark" aria-hidden="true"></span>
                        {:else}
                            <OverflowMenuHorizontal />
                        {/if}
                    {/snippet}
                    {#snippet children(close)}
                        {#each GROUPS as group (group)}
                            {@const tools = leftOut.filter(
                                (t) => t.group === group,
                            )}
                            {#if tools.length}
                                <p
                                    class="px-4 pt-2 text-label-01 text-text-secondary"
                                >
                                    {group}
                                </p>
                                {#each tools as tool (tool.id)}
                                    {@render menuRow(tool, close)}
                                {/each}
                            {/if}
                        {/each}
                    {/snippet}
                </OverflowMenu>
            {:else if !flat && modal(section.tools).length > 1}
                {@const tools = modal(section.tools)}
                {@const group = section.group}
                <ToolSlot
                    {group}
                    tool={shown(group, tools)}
                    tabindex={tab(group)}
                    listTabindex={tab(`${group}-list`)}
                >
                    {#snippet children(close)}
                        {#each tools as t (t.id)}
                            {@render menuRow(t, close)}
                        {/each}
                    {/snippet}
                </ToolSlot>
                {#each actions(section.tools) as action (action.id)}
                    {@render toolButton(action)}
                {/each}
            {:else}
                {#each section.tools as tool (tool.id)}
                    {@render toolButton(tool)}
                {/each}
            {/if}
        </div>
    {/each}
</div>

<style>
    /* The corner mark on ⋯ while it shows a tool armed from its list. */
    .flyout-mark {
        position: absolute;
        right: 2px;
        bottom: 2px;
        border-left: 5px solid transparent;
        border-bottom: 5px solid var(--color-icon-secondary);
    }
</style>
