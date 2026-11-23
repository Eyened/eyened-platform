<!--
@component
The set's move and its "Set status" menu as one combo button, in the header and, below md, in Grading's footer.
Ready is picked only once everything else saved; a pick that can't save shows on the button and nothing stays queued.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { ComboButton } from "$lib/components/ui/combo-button/index.js";
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
        layout = "header",
    }: {
        subTaskId: number;
        index: number;
        count: number;
        showStatus: boolean;
        navigation: SetNavigation;
        /** "stacked" in the narrow footer: full width, the failure in words under it. */
        layout?: "header" | "stacked";
        status: DebouncedSaver<SubTaskState>;
    } = $props();

    const items = SUBTASK_STATES.map((id) => ({
        id,
        label: SUBTASK_STATUS[id].label,
        description: SUBTASK_STATUS[id].description,
    }));
    const saved = $derived<SubTaskState>(
        subtasks.get(subTaskId)?.task_state ?? "NotStarted",
    );
    const last = $derived(index >= count - 1);
    // ASSUMPTION: words from xlg (82rem), as the header save state; below it the failure text is for screen readers.
    const xlg = new MediaQuery("min-width: 82rem");
    const invalidId = `${STATUS_ID}-invalid`;
    let picking = $state(false);
    // One pick at a time, and none once a move has started: its Ready or the page load would overtake it.
    const menuDisabled = $derived(picking || navigation.moving);

    async function pick(id: string) {
        if (menuDisabled) return;
        const state = id as SubTaskState;
        picking = true;
        try {
            // Ready means everything was saved, whichever control sets it. Focus stays on ▾.
            if (state === "Ready" && !(await flushWithin(saveTracker, 5000)))
                return;
            // A15: a failed save shows on the button; nothing stays queued.
            await navigation.saveStatus(state);
        } finally {
            picking = false;
        }
    }

    // A Ready set only moves on; the last set has nowhere to move to.
    const main = $derived.by(() => {
        if (!showStatus || saved === "Ready")
            return last ? null : { label: "Go to next set", markReady: false };
        return {
            label: last ? "Mark ready" : "Mark ready and next",
            markReady: true,
        };
    });
    const pending = $derived(navigation.pending === "primary");

    const stacked = $derived(layout === "stacked");

    function go() {
        if (main && !pending)
            void navigation.move("primary", {
                markReady: main.markReady,
                reopenPanel: stacked ? "forms" : undefined,
            });
    }
</script>

<div class={stacked ? "flex flex-col gap-2" : "contents"}>
    {#if showStatus}
        <ComboButton
            label={main?.label}
            onclick={go}
            {pending}
            data-set-control="primary"
            triggerId={STATUS_ID}
            triggerLabel="Set status: {SUBTASK_STATUS[saved].label}"
            heading="Set status"
            {items}
            selectedId={saved}
            onselect={pick}
            {menuDisabled}
            invalid={navigation.statusFailed}
            describedBy={invalidId}
            fullWidth={stacked}
        />
        <!-- Always mounted, so the text is announced when it appears. -->
        <span
            id={invalidId}
            role="alert"
            class="text-helper-text-01 text-text-error {stacked
                ? ''
                : xlg.current
                  ? 'whitespace-nowrap'
                  : 'sr-only'}"
            >{navigation.statusFailed
                ? "Status couldn't save. Pick it again."
                : ""}</span
        >
    {:else if main}
        <!-- Status off: only "Go to next set", tertiary, no menu. aria-disabled keeps focus on the button while it is pending. -->
        <Button
            variant="outline"
            size="sm"
            class={stacked ? "w-full" : undefined}
            data-set-control="primary"
            aria-disabled={pending || undefined}
            onclick={go}
        >
            {#if pending}
                <InlineLoading
                    class="text-inherit"
                    status="active"
                    description={main.label}
                    live={false}
                />
            {:else}
                {main.label}
            {/if}
        </Button>
    {/if}
</div>
