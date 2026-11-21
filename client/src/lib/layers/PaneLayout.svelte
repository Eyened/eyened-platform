<!--
@component
The Layers tab's list above the Selected pane, with a splitter between them. The pane fits its content up to half the tab until the user sets a height, which is kept per browser and clamped to the tab.
-->
<script lang="ts">
    import Splitter from "$lib/workspace/Splitter.svelte";
    import {
        readPaneHeight,
        writePaneHeight,
    } from "$lib/workspace/workspacePrefs";
    import type { LayersTarget } from "$lib/workspace/workspace.svelte";
    import type { Snippet } from "svelte";
    import {
        LIST_MIN_PX,
        PANE_MIN_PX,
        PANE_STEP_PX,
        paneHeight,
    } from "./paneHeight";
    import SelectedPane from "./SelectedPane.svelte";

    let { target, children }: { target: LayersTarget; children: Snippet } =
        $props();
    const uid = $props.id();
    let saved: number | null = $state(readPaneHeight());
    let tabHeight = $state(0);
    // The pane's height on screen: the user's, else what fit-content laid out.
    let shown = $state(0);
    let before: number | null = null;
    let start = 0;
    const set = $derived(paneHeight(saved, tabHeight));
    const max = $derived(Math.max(PANE_MIN_PX, tabHeight - LIST_MIN_PX));

    function keep(px: number) {
        saved = Math.round(px);
        writePaneHeight(saved);
    }
</script>

<div
    class="relative flex min-h-0 flex-1 flex-col"
    bind:clientHeight={tabHeight}
>
    <!-- pb-3 keeps the last row clear of the splitter's hit area, which reaches 12 px into the list. -->
    <div class="min-h-0 flex-1 overflow-y-auto pb-3" data-layers-list>
        {@render children()}
    </div>
    <!-- 24 px hit area centred on the line (WCAG 2.5.8); no double-click, which would collide with pick-up. -->
    <Splitter
        axis="row"
        label="Pane height"
        controls="{uid}-pane"
        thickness={24}
        valueNow={Math.max(PANE_MIN_PX, Math.round(shown))}
        valueMin={PANE_MIN_PX}
        valueMax={max}
        style="left: 0; right: 0; bottom: {shown - 12}px;"
        ondragstart={() => {
            before = saved;
            start = shown;
        }}
        ondrag={(delta) =>
            (saved = paneHeight(Math.round(start - delta), tabHeight))}
        ondragend={() => writePaneHeight(saved)}
        oncancel={() => (saved = before)}
        onstep={(direction) => keep(shown - direction * PANE_STEP_PX)}
        onlimit={(end) => keep(end === "min" ? PANE_MIN_PX : max)}
        onreset={() => {
            saved = null;
            writePaneHeight(null);
        }}
    />
    <div
        id="{uid}-pane"
        data-slot="selected-pane"
        class="flex flex-none flex-col overflow-hidden border-t border-border-subtle-01"
        style={set === null ? "max-height: 50%;" : `height: ${set}px;`}
        bind:offsetHeight={shown}
    >
        <SelectedPane {target} />
    </div>
</div>
