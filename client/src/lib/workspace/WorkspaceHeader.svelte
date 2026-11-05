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
    import LayoutPopover from "./LayoutPopover.svelte";
    import OverflowMenu from "./OverflowMenu.svelte";

    let { task, narrow }: { task: TaskHeader | null; narrow: boolean } =
        $props();
</script>

<header
    class="flex h-12 min-w-0 items-center gap-1 border-b border-border-subtle-01 bg-background pe-2"
    style="grid-area: header"
>
    <span class="px-4 text-heading-compact-01 text-text-primary">EyeNED</span>
    <!-- ASSUMPTION: reserved slots in the overview's order (plan decision 23). Patient context: 6; mode: 3. -->
    <div class="contents" data-header-slot="patient-context"></div>
    <div class="contents" data-header-slot="mode"></div>
    {#if task}
        <span class="text-body-compact-01 whitespace-nowrap text-text-primary"
            >{task.label}</span
        >
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
    <!-- In a task, the task config sets the strip. -->
    <LayoutPopover iconOnly={narrow} stripToggle={task === null} />
    {#if task && narrow}
        <OverflowMenu label="More">
            {#snippet children(close)}
                <Button
                    variant="ghost"
                    size="sm"
                    onclick={() => {
                        close();
                        task.overview();
                    }}
                >
                    Task overview
                </Button>
            {/snippet}
        </OverflowMenu>
    {/if}
</header>
