<!--
@component
The selected item's options under the Layers list: a fixed header, then a scrolling body. Nothing selected says what to do.
It owns the delete dialogs: a delete empties the selection and unmounts the body, so a dialog there would go before its "Deleted" state and its close.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { formAnnotations } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
    import { getContext } from "svelte";
    import type { LayersTarget } from "$lib/workspace/workspace.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import { focusAfterDelete } from "./focusAfterDelete";
    import GridDeleteModal from "./GridDeleteModal.svelte";
    import GridPane from "./pane/GridPane.svelte";
    import LinePane from "./pane/LinePane.svelte";
    import PointsetPane from "./pane/PointsetPane.svelte";
    import SegmentationPane from "./pane/SegmentationPane.svelte";
    import RegistrationDeleteModal from "./RegistrationDeleteModal.svelte";
    import SegmentationDeleteModal from "./SegmentationDeleteModal.svelte";

    let { target }: { target: LayersTarget } = $props();
    const uid = $props.id();
    const globalContext = getContext<GlobalContext>("globalContext");
    const selected = $derived(target.selection.value);
    // Delete shows where today's row shows its Delete icon.
    const canDelete = $derived.by(() => {
        const s = selected;
        if (!s) return false;
        if (s.kind === "line") return true;
        if (s.kind === "segmentation")
            return globalContext.canEdit(s.item.segmentation);
        const annotation = formAnnotations.get(s.id);
        return annotation !== undefined && globalContext.canEdit(annotation);
    });

    // The item being deleted, captured when Delete is pressed; it outlives the selection.
    type Deleting =
        | { kind: "segmentation"; segmentation: Segmentation }
        | { kind: "grid"; grid: FormAnnotationGET }
        | { kind: "pointset"; registration: FormAnnotationGET };
    let deleting: Deleting | null = $state.raw(null);
    let open = $state(false);
    let fallback = () => {};

    /** Read before the row goes: the selected row, else its type's section header. */
    function captureFocus(section: string) {
        const list = document.querySelector("[data-layers-list]");
        fallback = focusAfterDelete(
            list?.querySelector("[data-layer-row].selected") ?? null,
            list?.querySelector(`[data-layer-section="${section}"]`) ?? null,
        );
    }

    function askDelete() {
        const s = selected;
        if (!s) return;
        if (s.kind === "line") {
            captureFocus("distance");
            s.lines.remove(s.line);
            fallback();
            return;
        }
        if (s.kind === "segmentation") {
            captureFocus("segmentations");
            deleting = {
                kind: "segmentation",
                segmentation: s.item.segmentation,
            };
        } else {
            const annotation = formAnnotations.get(s.id);
            if (!annotation) return;
            captureFocus(s.kind === "grid" ? "etdrs" : "pointsets");
            deleting =
                s.kind === "grid"
                    ? { kind: "grid", grid: annotation }
                    : { kind: "pointset", registration: annotation };
        }
        open = true;
    }
</script>

{#snippet remove()}
    <IconButton size="icon-xs" label="Delete" onclick={askDelete}
        ><TrashCan /></IconButton
    >
{/snippet}

{#if !selected}
    <p class="px-4 py-3 text-body-compact-01 text-text-secondary">
        Select a layer to see its options.
    </p>
{:else}
    <section aria-labelledby="{uid}-name" class="flex min-h-0 flex-1 flex-col">
        {#if selected.kind === "segmentation"}
            {#key selected.item}
                <SegmentationPane
                    id="{uid}-name"
                    item={selected.item}
                    remove={canDelete ? remove : undefined}
                />
            {/key}
        {:else if selected.kind === "grid"}
            <GridPane
                id="{uid}-name"
                gridId={selected.id}
                remove={canDelete ? remove : undefined}
            />
        {:else if selected.kind === "pointset"}
            <PointsetPane
                id="{uid}-name"
                pointsetId={selected.id}
                remove={canDelete ? remove : undefined}
            />
        {:else}
            <LinePane
                id="{uid}-name"
                line={selected.line}
                lines={selected.lines}
                scale={target.scale}
                {remove}
            />
        {/if}
    </section>
{/if}
{#if deleting?.kind === "segmentation"}
    <SegmentationDeleteModal
        segmentation={deleting.segmentation}
        segmentationContext={target.mainViewerContext.segmentationContext}
        bind:open
        onfallback={() => fallback()}
    />
{:else if deleting?.kind === "grid"}
    <GridDeleteModal
        grid={deleting.grid}
        grids={target.grids}
        bind:open
        onfallback={() => fallback()}
    />
{:else if deleting?.kind === "pointset"}
    <RegistrationDeleteModal
        registration={deleting.registration}
        bind:open
        onfallback={() => fallback()}
    />
{/if}
