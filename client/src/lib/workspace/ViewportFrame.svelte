<!--
@component
One viewport: title bar, selection, empty state and title-bar drag. The image viewer comes in as a snippet.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import Maximize from "carbon-icons-svelte/lib/Maximize.svelte";
    import Minimize from "carbon-icons-svelte/lib/Minimize.svelte";
    import { getContext, tick, type Snippet } from "svelte";
    import { IMAGE_MIME, SLOT_MIME } from "./dragTypes";
    import { titleText, type ViewportTitle } from "./imageMeta";
    import OverflowMenu from "./OverflowMenu.svelte";
    import type { Workspace } from "./workspace.svelte";
    import type { Slot } from "./workspaceRules";

    let {
        id,
        position,
        slot,
        title,
        mode,
        style,
        viewer,
        onchooseimage,
    }: {
        id: string;
        position: number;
        slot: Slot;
        title: ViewportTitle | null;
        mode: "grid" | "big" | "tile" | "hidden";
        style: string;
        viewer: Snippet<[string]>;
        onchooseimage: () => void;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const selected = $derived(workspace.selected === position);
    const maximised = $derived(workspace.maximised === position);
    // ASSUMPTION: the selected viewport's controls follow it in Tab order (plan decision 2).
    const tab = $derived(selected ? 0 : -1);
    const shownTitle = $derived(slot.imageId ? title : null);
    const emptyTitle = $derived(workspace.loaded ? "Empty" : "Loading…");
    const name = $derived(
        `Viewport ${position + 1}: ${shownTitle ? titleText(shownTitle) : emptyTitle}`,
    );
    let dropTarget = $state(false);
    let titleOpen = $state(false);

    function onfocusin(e: FocusEvent) {
        workspace.select(position);
        // A press focuses the viewport too; only keyboard focus opens the title tooltip.
        if (shownTitle && (e.target as Element).matches(":focus-visible"))
            titleOpen = true;
    }

    function onfocusout(e: FocusEvent) {
        if (!(e.currentTarget as Node).contains(e.relatedTarget as Node | null))
            titleOpen = false;
    }

    async function onkeydown(e: KeyboardEvent) {
        if (e.key !== "PageUp" && e.key !== "PageDown") return;
        const delta = e.key === "PageUp" ? -1 : 1;
        const frame = e.currentTarget as HTMLElement;
        if (e.shiftKey) workspace.turnPage(workspace.page + delta);
        else workspace.stepFrameSet(delta);
        e.preventDefault();
        // A new image rebuilds the viewer and drops its focus; focus moves to the new viewer, or to Choose an image.
        await tick();
        if (!frame.contains(document.activeElement)) {
            frame
                .querySelector<HTMLElement>(".body [tabindex], .body button")
                ?.focus();
            // The title bar already shows the new image; the tooltip would cover the viewport above.
            titleOpen = false;
        }
    }

    function onclick(e: MouseEvent) {
        if (mode !== "tile" || (e.target as Element).closest("button")) return;
        workspace.setMaximised(position);
    }

    function choose() {
        workspace.select(position);
        onchooseimage();
    }

    function ondragstart(e: DragEvent) {
        if (!slot.imageId || !e.dataTransfer) {
            e.preventDefault();
            return;
        }
        e.dataTransfer.setData(SLOT_MIME, String(position));
        e.dataTransfer.effectAllowed = "move";
    }

    function accepts(e: DragEvent): boolean {
        const types = e.dataTransfer?.types ?? [];
        return types.includes(SLOT_MIME) || types.includes(IMAGE_MIME);
    }

    function ondragover(e: DragEvent) {
        if (!accepts(e)) return;
        e.preventDefault();
        dropTarget = true;
    }

    function ondragleave(e: DragEvent) {
        if (!(e.currentTarget as Node).contains(e.relatedTarget as Node | null))
            dropTarget = false;
    }

    function ondrop(e: DragEvent) {
        dropTarget = false;
        const data = e.dataTransfer;
        if (!data) return;
        const from = data.getData(SLOT_MIME);
        const imageId = data.getData(IMAGE_MIME);
        if (from !== "") {
            e.preventDefault();
            workspace.swap(Number(from), position);
        } else if (imageId) {
            e.preventDefault();
            workspace.load(position, imageId);
            workspace.select(position);
        }
    }
</script>

<!-- A strip tile's click is a shortcut for its Maximise button; the frame forwards keys from the viewer inside it. -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
    {id}
    role="group"
    aria-label={name}
    aria-current={selected ? "true" : undefined}
    data-mode={mode}
    class="frame"
    class:selected
    class:drop-target={dropTarget}
    {style}
    onpointerdowncapture={() => workspace.select(position)}
    {onfocusin}
    {onfocusout}
    {onkeydown}
    {onclick}
    {ondragover}
    {ondragleave}
    {ondrop}
>
    <div class="body">
        {#if slot.imageId}
            {#key slot.imageId}
                {@render viewer(slot.imageId)}
            {/key}
        {:else}
            <div class="empty">
                {#if workspace.loaded}
                    <p class="text-body-compact-01 text-text-secondary">
                        Empty
                    </p>
                    <Button variant="ghost" size="sm" onclick={choose}
                        >Choose an image</Button
                    >
                {:else}
                    <InlineLoading
                        status="active"
                        description="Loading images…"
                        class="w-auto"
                    />
                {/if}
            </div>
        {/if}
    </div>
    <!-- The title bar is a mouse-only drag handle; without a drag, swap is two loads from the Images panel. -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="titlebar" draggable={slot.imageId !== null} {ondragstart}>
        <Tooltip.Provider delayDuration={100}>
            <Tooltip.Root bind:open={titleOpen}>
                <Tooltip.Trigger>
                    {#snippet child({ props })}
                        <span {...props} tabindex="-1" class="title-text">
                            {#if shownTitle}
                                <span class="patient">{shownTitle.patient}</span
                                >
                                <span class="rest">{shownTitle.rest}</span>
                            {:else}
                                <span class="rest">{emptyTitle}</span>
                            {/if}
                        </span>
                    {/snippet}
                </Tooltip.Trigger>
                {#if shownTitle}
                    <Tooltip.Content>{titleText(shownTitle)}</Tooltip.Content>
                {/if}
            </Tooltip.Root>
        </Tooltip.Provider>
        <span class="controls">
            <!-- Sub-project 2 adds the link chip here. Maximise never folds; below 260 px only Close does. -->
            <IconButton
                size="icon-xs"
                label="Maximise"
                aria-pressed={maximised}
                tabindex={tab}
                onclick={() => workspace.toggleMaximise(position)}
            >
                {#if maximised}<Minimize />{:else}<Maximize />{/if}
            </IconButton>
            <span class="wide-only">
                <IconButton
                    size="icon-xs"
                    label="Close"
                    tabindex={tab}
                    onclick={() => workspace.close(position)}
                >
                    <Close />
                </IconButton>
            </span>
            <span class="narrow-only">
                <OverflowMenu label="More" size="icon-xs" tabindex={tab}>
                    {#snippet children(close)}
                        <Button
                            variant="ghost"
                            size="sm"
                            onclick={() => {
                                // Focus returns to ⋯, which stays in the emptied, selected slot (V-038), as ✕ keeps focus when wide.
                                close();
                                workspace.close(position);
                            }}
                        >
                            Close
                        </Button>
                    {/snippet}
                </OverflowMenu>
            </span>
        </span>
    </div>
</div>

<style>
    .frame {
        position: relative;
        display: flex;
        flex-direction: column;
        min-width: 0;
        min-height: 0;
        container-type: inline-size;
        box-shadow: 0 0 0 1px var(--color-border-subtle-01);
    }
    .frame::after {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        z-index: 3;
    }
    .frame.selected::after,
    .frame.drop-target::after {
        box-shadow: inset 0 0 0 2px var(--color-border-interactive);
    }
    .frame:has(:focus-visible)::before {
        content: "";
        position: absolute;
        inset: 2px;
        outline: 2px solid var(--color-focus);
        outline-offset: -2px;
        pointer-events: none;
        z-index: 3;
    }
    .titlebar {
        order: -1;
        flex: none;
        display: flex;
        align-items: center;
        gap: 0.25rem;
        height: 1.5rem;
        padding-inline-start: 0.5rem;
        background: var(--color-layer-01);
        cursor: grab;
        user-select: none;
    }
    .titlebar:active {
        cursor: grabbing;
    }
    .title-text {
        display: flex;
        flex: 1 1 0;
        min-width: 0;
        gap: 0.5rem;
        overflow: hidden;
        white-space: nowrap;
        font-size: var(--text-label-01);
        line-height: 1.5rem;
    }
    .patient {
        flex: none;
        color: var(--color-text-primary);
    }
    .rest {
        flex: 1 1 0;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        color: var(--color-text-secondary);
    }
    .controls,
    .wide-only {
        display: flex;
        flex: none;
    }
    .narrow-only {
        display: none;
    }
    @container (max-width: 259px) {
        .wide-only {
            display: none;
        }
        .narrow-only {
            display: flex;
        }
    }
    .body {
        position: relative;
        display: flex;
        flex: 1;
        min-height: 0;
        /* The viewer never grows past its frame. */
        overflow: hidden;
    }
    .body > :global(*) {
        min-width: 0;
    }
    .empty {
        display: flex;
        flex: 1;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
    }
</style>
