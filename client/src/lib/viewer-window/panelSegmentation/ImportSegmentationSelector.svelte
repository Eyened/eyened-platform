<script lang="ts">
    import type { Annotation } from "$lib/datamodel/annotation.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";

    interface Props {
        image: AbstractImage;
        annotation: Annotation;
        resolve: (annotation: Annotation) => void;
        reject: () => void;
    }

    let { image, annotation, resolve, reject }: Props = $props();
    const segmentationAnnotations = image.instance.annotations;
    const referenceAnnotations = segmentationAnnotations.filter(
        (a) => a.id != annotation.id,
    );
</script>

<div>Select annotation to import from:</div>
<ul>
    {#each $referenceAnnotations as annotation}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <li onclick={() => resolve(annotation)}>
            <div class="annotation-id">
                [{annotation.id}]
            </div>
            <div>{annotation.creator.name}</div>
            <div>{annotation.feature.name}</div>
        </li>
    {/each}
</ul>
<button onclick={reject}>Cancel</button>

<style>
    ul {
        display: grid;
        grid-template-columns: 0fr 1fr 1fr;

        list-style-type: none;
        padding: 0;
        max-height: 20em;
        overflow: auto;
    }

    li {
        display: contents;
        cursor: pointer;
    }

    div.annotation-id {
        font-size: x-small;
        color: gray;
    }
    li > div {
        padding: 0.5em;
        align-items: center;
        display: flex;
        border-bottom: 1px solid rgba(0, 0, 0, 0.2);
    }
    li.hover > div {
        background-color: #e6fdff;
    }
    li.selected > div {
        background-color: #43ff46;
    }
</style>
