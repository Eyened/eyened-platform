<!--
@component
The set's Status Dropdown and its primary button, in the header (and the narrow footer later).
Ready is picked only once everything else saved; a pick that can't save goes back.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { subtasks } from "$lib/data/stores.svelte";
    import type { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
    import { saveTracker } from "$lib/saving/saveTracker.svelte";
    import { MediaQuery } from "svelte/reactivity";
    import type { SubTaskState } from "../../types/openapi_types";
    import {
        flushWithin,
        STATUS_ID,
        type SetNavigation,
    } from "./setNavigation.svelte";
    import { SUBTASK_STATES, SUBTASK_STATUS } from "./subtaskStatus";

    let {
        subTaskId,
        index,
        count,
        showStatus,
        navigation,
    }: {
        subTaskId: number;
        index: number;
        count: number;
        showStatus: boolean;
        navigation: SetNavigation;
        status: DebouncedSaver<SubTaskState>;
    } = $props();

    const items = SUBTASK_STATES.map((id) => ({
        id,
        text: SUBTASK_STATUS[id].label,
    }));
    const saved = $derived<SubTaskState>(
        subtasks.get(subTaskId)?.task_state ?? "NotStarted",
    );
    // The Dropdown's pick; back to the saved value when it can't be saved.
    let picked = $derived<string>(saved);
    const last = $derived(index >= count - 1);
    // ASSUMPTION: words from xlg (82rem), as the header save state; below it the invalid text is for screen readers.
    const xlg = new MediaQuery("min-width: 82rem");

    async function pick(next: string) {
        const state = next as SubTaskState;
        // Ready means everything was saved, whichever control sets it. Focus stays on the Dropdown.
        if (state === "Ready" && !(await flushWithin(saveTracker, 5000))) {
            picked = saved;
            return;
        }
        // A15: a failed save goes back and shows on the Dropdown; nothing stays queued.
        if (!(await navigation.saveStatus(state))) picked = saved;
    }

    const primary = $derived.by(() => {
        if (!showStatus || saved === "Ready")
            return last
                ? null
                : {
                      text: "Go to next set",
                      variant: "outline" as const,
                      markReady: false,
                  };
        return {
            text: last ? "Mark ready" : "Mark ready and next",
            variant: "default" as const,
            markReady: true,
        };
    });
    const pending = $derived(navigation.pending === "primary");

    // aria-disabled keeps focus on the button while it is pending.
    function go() {
        if (primary && !pending)
            void navigation.move("primary", { markReady: primary.markReady });
    }
</script>

{#if showStatus}
    <Dropdown
        id={STATUS_ID}
        type="inline"
        size="sm"
        labelText="Status"
        {items}
        bind:selectedId={() => picked, (v) => (picked = v ?? saved)}
        onselect={pick}
        invalid={navigation.statusFailed}
        invalidText="Status couldn't save. Pick it again."
        hideInvalidText={!xlg.current}
    />
{/if}
{#if primary}
    <Button
        variant={primary.variant}
        size="sm"
        data-set-control="primary"
        aria-disabled={pending || undefined}
        onclick={go}
    >
        {#if pending}
            <InlineLoading
                class="text-inherit"
                status="active"
                description={primary.text}
                live={false}
            />
        {:else}
            {primary.text}
        {/if}
    </Button>
{/if}
