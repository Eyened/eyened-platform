<script lang="ts">
    import { deleteFormAnnotation } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte"
    import type { FormAnnotationGET } from "../../../types/openapi_types"
    import type { Position2D } from "$lib/types"
    import type { ETDRSGridOverlay } from "$lib/viewer/overlays/ETDRSGridOverlay.svelte"
    import type { ETDRSGridTool } from "$lib/viewer/tools/ETDRSGrid.svelte"
    import { getContext } from "svelte"
    import { Edit, Hide, PanelIcon, Show, Trash } from "../icons/icons"

    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        overlay: ETDRSGridOverlay;
        tool: ETDRSGridTool;
        formAnnotation: FormAnnotationGET;
    }
    let { overlay, tool, formAnnotation }: Props = $props();

    let fovea: Position2D | undefined = $derived(formAnnotation.form_data?.fovea as Position2D | undefined);
    let disc_edge: Position2D | undefined = $derived(
        formAnnotation.form_data?.disc_edge as Position2D | undefined,
    );

    // Note: overlay/tool expect old FormAnnotation type, will be fixed when overlays are refactored
    let show = $derived(overlay.visible.has(formAnnotation as any));
    let active = $derived(tool.annotation?.id == formAnnotation.id);

    const canEditForm = globalContext.canEdit(formAnnotation);

    function toggleVisisble() {
        if (overlay.visible.has(formAnnotation as any)) {
            overlay.visible.delete(formAnnotation as any);
        } else {
            overlay.visible.add(formAnnotation as any);
        }
    }

    function edit() {
        if (tool.annotation?.id == formAnnotation.id) {
            tool.annotation = undefined;
        } else {
            overlay.visible.add(formAnnotation as any);
            tool.annotation = formAnnotation as any;
        }
    }

    function remove() {
        overlay.visible.delete(formAnnotation as any);
        if (tool.annotation?.id == formAnnotation.id) {
            tool.annotation = undefined;
        }
        deleteFormAnnotation(formAnnotation.id);
    }

    let showHide = $derived(show ? Show : Hide);
</script>

{#snippet coordinate(label: string, property: Position2D)}
    <li>
        <span>{label}:</span>
        <span>
            [{Math.round(property.x)}, {Math.round(property.y)}]
        </span>
    </li>
{/snippet}

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="info">
    <span class="annotation-id">[{formAnnotation.id}]</span>
    <div class="top">
        <PanelIcon
            active={show}
            onclick={toggleVisisble}
            tooltip="show/hide"
            Icon={showHide}
        />

        {#if canEditForm}
            <PanelIcon {active} onclick={edit} tooltip="edit" Icon={Edit} />
        {/if}
        {#if canEditForm}
            <div class="spacer"></div>
            <PanelIcon onclick={remove} tooltip="delete" Icon={Trash} />
        {/if}
    </div>
    <ul>
        {#if fovea}
            {@render coordinate("fovea", fovea)}
        {/if}
        {#if disc_edge}
            {@render coordinate("disc_edge", disc_edge)}
        {/if}
    </ul>
</div>

<style>
    .info {
        display: flex;
        background-color: rgba(255, 255, 255, 0.1);
        flex-direction: column;
        border: 1px solid black;
        border-radius: 2px;
        padding: 0.2em;
    }
    .info:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }
    div.top {
        display: flex;
    }
    span.annotation-id {
        font-size: x-small;
    }
    div.spacer {
        flex: 1;
    }
    ul {
        list-style-type: none;
        padding: 0;
        margin: 0;
        font-size: small;
    }
    li {
        display: flex;
        align-items: center;
    }
    li * {
        flex: 1;
    }
</style>
