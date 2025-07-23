<script lang="ts">
    import type { Position2D } from "$lib/types";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { getContext } from "svelte";
    import { Edit, Hide, PanelIcon, Show, Trash } from "../icons/icons";
    import type { ETDRSGridOverlay } from "$lib/viewer/overlays/ETDRSGridOverlay.svelte";
    import type { ETDRSGridTool } from "$lib/viewer/tools/ETDRSGrid.svelte";
    import type { FormAnnotation } from "$lib/datamodel/formAnnotation.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        overlay: ETDRSGridOverlay;
        tool: ETDRSGridTool;
        formAnnotation: FormAnnotation;
    }
    let { overlay, tool, formAnnotation }: Props = $props();

    let fovea: Position2D | undefined = $derived(formAnnotation.value?.fovea);
    let disc_edge: Position2D | undefined = $derived(
        formAnnotation.value?.disc_edge,
    );

    let show = $derived(overlay.visible.has(formAnnotation));
    let active = $derived(tool.annotation?.id == formAnnotation.id);

    const canEditForm = globalContext.canEdit(formAnnotation);

    function toggleVisisble() {
        if (overlay.visible.has(formAnnotation)) {
            overlay.visible.delete(formAnnotation);
        } else {
            overlay.visible.add(formAnnotation);
        }
    }

    function edit() {
        if (tool.annotation?.id == formAnnotation.id) {
            tool.annotation = undefined;
        } else {
            overlay.visible.add(formAnnotation);
            tool.annotation = formAnnotation;
        }
    }

    function remove() {
        overlay.visible.delete(formAnnotation);
        if (tool.annotation?.id == formAnnotation.id) {
            tool.annotation = undefined;
        }
        formAnnotation.delete();
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
