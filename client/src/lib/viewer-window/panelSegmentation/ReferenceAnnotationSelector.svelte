<script lang="ts">
    import type { Annotation } from "$lib/datamodel/_annotation.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext } from "svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    interface Props {
        image: AbstractImage;
        annotation: Annotation;
        resolve: (annotation: Annotation) => void;
        reject: () => void;
    }

    let { image, annotation, resolve, reject }: Props = $props();
    const segmentationAnnotations = image.instance.annotations.filter(globalContext.annotationsFilter);
    const referenceAnnotations = segmentationAnnotations.filter(
        (a) => {
            if (a.annotationType.dataRepresentation == "MultiLabel" || a.annotationType.dataRepresentation == "MultiClass" || a.annotationType.dataRepresentation == "Probability") return false;
            return true;
        },
    );
    
</script>

<div>
    <div>Select reference annotation:</div>
    <ul>
        {#each $referenceAnnotations as referenceAnnotation}
            {@const current =
                referenceAnnotation.id == annotation.annotationReferenceId}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
            <li onclick={() => resolve(referenceAnnotation)} class:current>

                <span>[{referenceAnnotation.id}]</span>
                <span>{referenceAnnotation.feature.name}</span>
                <span>{referenceAnnotation.creator.name}</span>
            </li>
        {/each}
    </ul>
    <button onclick={reject}>Cancel</button>
</div>

<style>
    ul {
        list-style-type: none;
        padding: 0;
    }
    li {
        padding: 0.5em;
        border-bottom: 1px solid #ccc;
        cursor: pointer;
    }
    li.current {
        background-color: #f0fff0;
    }
    li:hover {
        background-color: #f0f0f0;
    }
</style>
