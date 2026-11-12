<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { Toggle } from "$lib/components/ui/toggle/index.js";
    import { updateSegmentation } from "$lib/data/api";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { segmentations } from "$lib/data/stores.svelte";
    import SegmentationPickerModal from "$lib/layers/SegmentationPickerModal.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { SegmentationItem } from "$lib/webgl/segmentationItem.svelte";
    import { getContext } from "svelte";
    import type { SegmentationGET } from "../../../types/openapi_types";
    import type { Segmentation } from "./segmentationContext.svelte";
    import { orderSegmentationsByCreator } from "./segmentationUtils";

    interface Props {
        segmentation: SegmentationGET;
        isEditable: boolean;
        segmentationItem: SegmentationItem;
    }
    let { segmentation, isEditable, segmentationItem }: Props = $props();

    const mainViewerContext =
        getContext<MainViewerContext>("mainViewerContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const me = globalContext.user.id;
    const uid = $props.id();
    let open = $state(false);
    let opener = $state<HTMLElement | null>(null);

    const referenceId = $derived(
        segmentation.reference_segmentation_id ?? null,
    );
    const referenceText = $derived.by(() => {
        if (referenceId === null) return "";
        const reference = segmentations.get(referenceId);
        if (!reference) return `[${referenceId}]`;
        const author =
            reference.creator.id === me ? "Mine" : reference.creator.name;
        return `${reference.feature.name} · ${author} · ${referenceId}`;
    });
    // Grader Binary and Questionable rows on this plane, the grader's own first, never the row itself.
    const rows = $derived(
        orderSegmentationsByCreator(
            [],
            mainViewerContext.segmentationContext.graderSegmentations,
            me,
        ).filter(
            (s) =>
                s.id !== segmentation.id &&
                (s.data_representation === "Binary" ||
                    s.data_representation === "DualBitMask"),
        ),
    );
    const masking = $derived(mainViewerContext.isMaskingApplied(segmentation));

    function setReference(other: Segmentation) {
        return updateSegmentation(segmentation.id, {
            reference_segmentation_id: other.id,
        });
    }

    // Remove unmounts itself, so focus moves to the opener, which stays mounted.
    async function removeReference() {
        await updateSegmentation(segmentation.id, {
            reference_segmentation_id: null,
        });
        opener?.focus();
    }
</script>

{#if referenceId !== null || isEditable}
    <section class="flex flex-col gap-3" aria-labelledby="{uid}-heading">
        <h5
            id="{uid}-heading"
            class="text-heading-compact-01 text-text-primary"
        >
            Reference mask
        </h5>
        {#if referenceId !== null}
            <p class="text-body-compact-01 text-text-primary">
                {referenceText}
            </p>
        {/if}
        {#if isEditable}
            <!-- One opener for Set reference… and Change…, so the modal can return focus to it. -->
            <div class="flex">
                <Button
                    variant="ghost"
                    size="sm"
                    bind:ref={opener}
                    onclick={() => (open = true)}
                    >{referenceId === null
                        ? "Set reference…"
                        : "Change…"}</Button
                >
                {#if referenceId !== null}
                    <Button variant="ghost" size="sm" onclick={removeReference}
                        >Remove</Button
                    >
                {/if}
            </div>
        {/if}
        {#if referenceId !== null}
            <Field.Field orientation="horizontal">
                <Toggle
                    id="{uid}-mask"
                    bind:checked={
                        () => masking,
                        () => mainViewerContext.toggleMasking(segmentationItem)
                    }
                />
                <Field.Label
                    for="{uid}-mask"
                    class="text-body-compact-01 text-text-primary"
                    >Mask with reference</Field.Label
                >
            </Field.Field>
        {/if}
    </section>
    <SegmentationPickerModal
        bind:open
        modalHeading="Set reference mask"
        modalLabel="{segmentation.feature.name} [{segmentation.id}]"
        primaryButtonText="Set reference"
        primaryButtonLoadingDescription="Setting…"
        successDescription="Reference set"
        errorTitle="Reference could not be set"
        {rows}
        currentId={referenceId}
        emptyTitle="No reference available"
        emptyDescription="No other Binary or Questionable segmentation on this plane."
        onpick={setReference}
    />
{/if}
