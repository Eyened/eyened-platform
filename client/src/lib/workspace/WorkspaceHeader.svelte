<script module lang="ts">
    /** Task-mode set navigation, built from today's TaskNavigation. */
    export interface TaskHeader {
        label: string;
        prevDisabled: boolean;
        nextDisabled: boolean;
        prev(): void;
        next(): void;
        overview(): void;
    }
</script>

<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import ChevronLeft from "carbon-icons-svelte/lib/ChevronLeft.svelte";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import { ContentSwitcher } from "$lib/components/ui/content-switcher/index.js";
    import { getContext, type Snippet } from "svelte";
    import LayoutPopover from "./LayoutPopover.svelte";
    import type { ToolMode } from "./tools/registry";
    import type { Workspace } from "./workspace.svelte";
    import { writeToolMode } from "./workspacePrefs";

    // Below md the frame supplies the menu button (start) and the right-column button (end).
    let {
        task,
        narrow,
        start,
        end,
    }: {
        task: TaskHeader | null;
        narrow: boolean;
        start?: Snippet;
        end?: Snippet;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const MODES = [
        { id: "browse", text: "Browse" },
        { id: "all", text: "All tools" },
    ];

    function setMode(id: string) {
        workspace.toolMode = id as ToolMode;
        writeToolMode(workspace.toolMode);
    }
</script>

<header
    class="flex h-12 min-w-0 items-center gap-1 border-b border-border-subtle-01 bg-background pe-2"
    style="grid-area: header"
>
    {#if narrow}
        {@render start?.()}
    {:else}
        <span class="px-4 text-heading-compact-01 text-text-primary"
            >EyeNED</span
        >
    {/if}
    <!-- ASSUMPTION: reserved slots in the overview's order (plan decision 23). Patient context: 6; mode: 3. -->
    <div class="contents" data-header-slot="patient-context"></div>
    <div class="contents" data-header-slot="mode">
        {#if !task}
            <!-- A task is always All tools and shows no switcher. -->
            <ContentSwitcher
                size="sm"
                label="Mode"
                class="ms-2 w-fit"
                items={MODES}
                selectedId={workspace.toolMode}
                onchange={setMode}
            />
        {/if}
    </div>
    {#if task}
        {#if narrow}
            <!-- Below md "Set" is dropped from view to fit 320 px; ◀ ▶ still say "set". -->
            <span class="sr-only">{task.label}</span>
            <span
                aria-hidden="true"
                class="ps-2 text-body-compact-01 whitespace-nowrap text-text-primary"
                >{task.label.replace(/^Set /, "")}</span
            >
        {:else}
            <span
                class="text-body-compact-01 whitespace-nowrap text-text-primary"
                >{task.label}</span
            >
        {/if}
        <IconButton
            label="Previous set"
            disabled={task.prevDisabled}
            onclick={() => task.prev()}
        >
            <ChevronLeft />
        </IconButton>
        <IconButton
            label="Next set"
            disabled={task.nextDisabled}
            onclick={() => task.next()}
        >
            <ChevronRight />
        </IconButton>
        {#if !narrow}
            <Button variant="ghost" size="sm" onclick={() => task.overview()}
                >Task overview</Button
            >
        {/if}
    {/if}
    <div class="min-w-0 flex-1"></div>
    <div class="contents" data-header-slot="patients-open"></div>
    <!-- Save state: 4 and 5; "Mark ready and next": 5. -->
    <div class="contents" data-header-slot="save-state"></div>
    {#if task}
        <div class="contents" data-header-slot="mark-ready"></div>
    {/if}
    {#if narrow}
        {@render end?.()}
    {:else}
        <!-- In a task, the task config sets the strip. -->
        <LayoutPopover stripToggle={task === null} />
    {/if}
</header>
