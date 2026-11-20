<!--
@component
The New segmentation modal, from New › Advanced… or a drawn region box: Type, then Feature, then Placement.
The section remounts it for each open, so every open starts fresh.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { ComboBox } from "$lib/components/ui/combo-box/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { NumberInput } from "$lib/components/ui/number-input/index.js";
    import { RadioButtonGroup } from "$lib/components/ui/radio-button/index.js";
    import { features } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import {
        createSegmentationFromDialog,
        defaultRegionSize,
        isMultiSegmentationType,
        SEGMENTATION_TYPE_OPTIONS,
        type CreateSegmentationDialogMode,
        type SegmentationTypeChoice,
    } from "./createSegmentationHelpers";

    let { onfocusnew }: { onfocusnew: () => void } = $props();

    const uid = $props.id();
    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { segmentationContext } =
        getContext<MainViewerContext>("mainViewerContext");
    const { image, axis } = viewerContext;

    // Fixed for this open: the section remounts the modal for the next one.
    const box = segmentationContext.createDialog?.box;
    const size = box
        ? defaultRegionSize(box)
        : { width: image.width, height: image.height };

    // Closing keeps the content while the modal fades out; the next open remounts it.
    let open = $state(true);
    let type = $state<SegmentationTypeChoice>("Q");
    let placement = $state<CreateSegmentationDialogMode>(
        box ? "region" : "full",
    );
    let featureId = $state("");
    let featureText = $state("");
    let width = $state(String(size.width));
    let height = $state(String(size.height));
    let drawing = false;

    const typeItems = SEGMENTATION_TYPE_OPTIONS.map((o) => ({
        value: o.value,
        labelText: o.label,
    }));
    const placementItems = [
        { value: "full", labelText: "Full image" },
        { value: "region", labelText: "Region box" },
    ] as const;

    const multi = $derived(isMultiSegmentationType(type));
    const offered = $derived(
        multi
            ? features.filter((f) => (f.subfeatures ?? []).length > 0)
            : features.map((f) => f),
    );
    // After a pick the field shows its name, so the list then shows every offered feature.
    const items = $derived.by(() => {
        const q = featureId ? "" : featureText.trim().toLowerCase();
        return offered
            .filter((f) => f.name.toLowerCase().includes(q))
            .map((f) => ({ id: String(f.id), text: f.name }));
    });
    const canCreate = $derived(
        featureId !== "" && !(placement === "region" && !box),
    );

    const r = Math.round;
    const placementHelp = $derived(
        multi
            ? "Multi-class and multi-label cover the full image."
            : placement === "full"
              ? `Covers the full image (${image.width} × ${image.height} px).`
              : box
                ? `Box (${r(box.x0)}, ${r(box.y0)}) → (${r(box.x1)}, ${r(box.y1)}), ${r(box.x1 - box.x0)} × ${r(box.y1 - box.y0)} px on the image`
                : "No region drawn yet.",
    );

    // Multi-class and multi-label cover the full image and need a feature with subfeatures.
    function setType(next: SegmentationTypeChoice) {
        type = next;
        if (!isMultiSegmentationType(next)) return;
        placement = "full";
        if (featureId && !offered.some((f) => String(f.id) === featureId)) {
            featureId = "";
            featureText = "";
        }
    }

    // The box draw opens the modal again when it ends.
    function draw() {
        drawing = true;
        open = false;
        segmentationContext.regionToolActive = true;
    }

    // Advanced… closed with its popover, so focus goes to New; after a region draw it goes back to the image.
    function restoreFocus(event: Event) {
        event.preventDefault();
        if (box || drawing) viewerContext.canvas2D.parentElement?.focus();
        else onfocusnew();
    }

    function create() {
        const feature = features.get(Number(featureId));
        if (!feature) return false;
        segmentationContext.regionToolActive = false;
        // An earlier quick create's notice is stale once this one starts.
        segmentationContext.failed = null;
        return createSegmentationFromDialog(
            globalContext,
            segmentationContext,
            {
                image,
                axis,
                feature,
                subtaskId: taskContext?.subTask?.id,
                type,
                mode: placement,
                box: placement === "region" ? box : undefined,
                segWidth: Number(width),
                segHeight: Number(height),
            },
        );
    }
</script>

<Modal
    bind:open={
        () => open,
        (v) => {
            open = v;
            // Cancel, ✕ and Esc end any region draw too; Draw keeps it on.
            if (!v && !drawing) segmentationContext.regionToolActive = false;
        }
    }
    size="sm"
    modalLabel="Segmentations"
    modalHeading="New segmentation"
    primaryButtonText="Create"
    primaryButtonLoadingDescription="Creating…"
    successDescription="Created"
    errorTitle="Segmentation could not be created"
    primaryButtonDisabled={!canCreate}
    onsubmit={create}
    onCloseAutoFocus={restoreFocus}
>
    <div class="flex flex-col gap-6">
        <RadioButtonGroup
            legendText="Type"
            items={typeItems}
            bind:selected={() => type, setType}
            class="[&>div]:flex-col"
        />
        <ComboBox
            titleText="Feature"
            {items}
            bind:value={featureText}
            bind:selected={featureId}
            helperText={multi
                ? "Multi-class and multi-label offer features with subfeatures only."
                : undefined}
        />
        <div class="flex flex-col gap-2">
            <RadioButtonGroup
                legendText="Placement"
                items={placementItems}
                bind:selected={placement}
                disabled={multi}
                describedBy="{uid}-placement"
            />
            <p
                id="{uid}-placement"
                class="text-helper-text-01 text-text-helper"
            >
                {placementHelp}
            </p>
            {#if placement === "region" && !multi}
                <Button
                    variant="ghost"
                    size="sm"
                    class="self-start"
                    onclick={draw}
                    >{box ? "Redraw on image" : "Draw on image"}</Button
                >
                {#if box}
                    <div class="flex flex-wrap gap-4">
                        <NumberInput
                            labelText="Mask width (px)"
                            min="1"
                            bind:value={width}
                        />
                        <NumberInput
                            labelText="Mask height (px)"
                            min="1"
                            bind:value={height}
                        />
                    </div>
                {/if}
            {/if}
        </div>
    </div>
</Modal>
