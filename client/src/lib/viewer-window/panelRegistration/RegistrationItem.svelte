<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import {
    	type PointList
    } from "$lib/viewer/tools/Registration";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";
    import { PanelIcon, Trash } from "../icons/icons";

    interface Props {
        formAnnotation: FormAnnotationGET;
        active: boolean;
        onactivate: (annotation: FormAnnotationGET) => void;
        onremove: (annotation: FormAnnotationGET) => void;
    }
    let {
        formAnnotation,
        active,
        onactivate,
        onremove
    }: Props = $props();
    const globalContext = getContext<GlobalContext>("globalContext");
    const canEditForm = globalContext.canEdit(formAnnotation);
    
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const instance = viewerContext.image.instance;

    // Create a reactive derived value that will update when form_data changes
    const formDataEntries = $derived(() => {
        return Object.entries(formAnnotation.form_data || {}).map(([instanceID, pointSet]) => [
            instanceID, 
            (pointSet as PointList).map(point => point ? { ...point } : point)
        ]);
    });

</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<li class="outer" class:active onclick={() => onactivate(formAnnotation)}>
    <div class="info">
        <span class="creator">
            {formAnnotation.creator.name}
        </span>
        <span class="annotationID">[{formAnnotation.id}]</span>
        {#if canEditForm}
            <PanelIcon onclick={() => onremove(formAnnotation)} tooltip="Remove" Icon={Trash} />
        {/if}
    </div>
    {#if active}
        {#each formDataEntries() as [instanceID, pointSet]}
            <div>{instanceID}:</div>
            {#if instanceID === `${instance.id}`}
                <ol>
                    {#each pointSet as PointList as point, index}
                        {#if point}
                            <li class="point">
                                [{index + 1}]: [{point.x.toFixed(2)}, {point.y.toFixed(2)}]
                            </li>
                        {:else}
                            <li class="point">No point</li>
                        {/if}
                    {/each}
                </ol>
            {/if}
        {/each}
    {/if}
</li>

<style>
    div {
        display: flex;
    }
    div.info {
        align-items: center;
    }
    div.info * {
        display: flex;
    }
    .creator {
        flex: 1;
    }
    .annotationID {
        color: rgba(255, 255, 255, 0.4);
    }
    li.outer:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }
    li.outer {
        cursor: pointer;
        background-color: rgba(255, 255, 255, 0.1);
        padding-left: 0.5em;
        margin-bottom: 0.1em;
        border-radius: 1px;
    }
    li.outer.active {
        background-color: rgb(57, 158, 165);
        color: white;
    }
    li.point {
        font-size: 0.8em;
        padding-left: 1em;
    }
</style>
