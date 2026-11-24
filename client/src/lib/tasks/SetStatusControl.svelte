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
    import type { SetHolder } from "./holder.svelte";
    import {
        flushWithin,
        STATUS_ID,
        type SetNavigation,
    } from "./setNavigation.svelte";
    import { SUBTASK_STATES, SUBTASK_STATUS } from "./subtaskStatus";

    let {
        subTaskId,
        index,
        showStatus,
        navigation,
        holder,
        layout = "header",
    }: {
        subTaskId: number;
        /** This set's 0-based index. */
        index: number;
        showStatus: boolean;
        navigation: SetNavigation;
        holder: SetHolder;
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
    // "Last" for the primary move: no open set after this one.
    const last = $derived(
        (subtasks.get(subTaskId)?.next_open_index ?? null) === null,
    );
    const canEdit = $derived(holder.canEdit);
    // ASSUMPTION: words from xlg (82rem), as the header save state; below it the failure text is for screen readers.
    const xlg = new MediaQuery("min-width: 82rem");
    // Below lg (66rem), Claim / Give back are the menu's last item; the narrow footer is always below lg.
    const lg = new MediaQuery("min-width: 66rem");
    const claimInMenu = $derived(showStatus && !lg.current);
    const invalidId = `${STATUS_ID}-invalid`;
    let picking = $state(false);
    // One pick at a time, and none once a move has started: its Ready or the page load would overtake it.
    const menuDisabled = $derived(picking || navigation.moving || holder.busy);

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

    // A Ready set, or one I may not change, only moves on; with no open set after it there is nowhere to move to.
    const main = $derived.by(() => {
        if (!showStatus || !canEdit || saved === "Ready")
            return last ? null : { label: "Go to next set", markReady: false };
        return {
            label: last ? "Mark ready" : "Mark ready and next",
            markReady: true,
        };
    });
    const pending = $derived(navigation.pending === "primary");
    const action = $derived.by(() => {
        if (!claimInMenu || !holder.action) return undefined;
        const onselect = () => void holder.run();
        return holder.action === "claim"
            ? {
                  label: `Claim set ${index + 1}`,
                  description: "Others see that you hold it.",
                  onselect,
              }
            : {
                  label: `Give back set ${index + 1}`,
                  description: "Anyone on the task can then claim it.",
                  onselect,
              };
    });
    // Below lg a failed Claim or Give back shows on the combo button, as a failed status save does.
    const claimFailed = $derived(claimInMenu && holder.failText !== "");
    const failText = $derived(
        navigation.statusFailed
            ? "Status couldn't save. Pick it again."
            : claimFailed
              ? holder.failText
              : "",
    );

    const stacked = $derived(layout === "stacked");

    function go() {
        if (main && !pending)
            void navigation.move("primary", {
                markReady: main.markReady,
                reopenPanel: stacked ? "forms" : undefined,
            });
    }
</script>

<div class={stacked ? "flex flex-col" : "contents"}>
    {#if showStatus && canEdit}
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
            invalid={navigation.statusFailed || claimFailed}
            describedBy={invalidId}
            fullWidth={stacked}
            {action}
        />
        <!-- Always mounted, so the text is announced when it appears. -->
        <span
            id={invalidId}
            role="alert"
            class="text-helper-text-01 text-text-error {stacked
                ? failText
                    ? 'mt-2'
                    : ''
                : xlg.current
                  ? 'whitespace-nowrap'
                  : 'sr-only'}">{failText}</span
        >
    {:else if main}
        <!-- Status off, or a set I may not change: only "Go to next set", tertiary, no menu. aria-disabled keeps focus on the button while it is pending. -->
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
