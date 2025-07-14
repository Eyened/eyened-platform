<script lang="ts">
    import type { Annotation } from "$lib/datamodel/annotation.svelte";
    import { AnnotationTypeFeature } from "$lib/datamodel/annotationType.svelte";
    import { colors } from "$lib/viewer/overlays/colors";
    import type { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import { getContext } from "svelte";

    interface Props {
        annotation: Annotation;
    }
    let { annotation }: Props = $props();

    const { annotatedFeatures, dataRepresentation } = annotation.annotationType;
    const sortedFeatures = annotatedFeatures.sort(
        (a, b) => a.featureIndex - b.featureIndex,
    );

    const groupType = {
        MultiLabel: "checkbox",
        MultiClass: "radio",
    }[dataRepresentation as "MultiLabel" | "MultiClass"];

    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );

    const { segmentationContext } = segmentationOverlay;
    function pointerEnter(featureIndex: number) {
        segmentationOverlay.highlightedFeatureIndex = featureIndex;
    }
    function pointerLeave() {
        segmentationOverlay.highlightedFeatureIndex = undefined;
    }
    
</script>

{#snippet radioLabel(feature: AnnotationTypeFeature)}
    <label>
        <input
            type="radio"
            bind:group={segmentationContext.activeIndices}
            value={feature.featureIndex}
        />
        {feature.feature.name}
    </label>
{/snippet}
{#snippet checkboxLabel(feature: AnnotationTypeFeature)}
    <label>
        <input
            type="checkbox"
            bind:group={segmentationContext.activeIndices}
            value={feature.featureIndex}
        />
        {feature.feature.name}
    </label>
{/snippet}
<div>
    <ul>
        {#each $sortedFeatures as a}
            <li
                onpointerenter={()=>pointerEnter(a.featureIndex)}
                onpointerleave={pointerLeave}
            >
                <div class="feature-container">
                    <div
                        class="color-box"
                        style="background-color: rgb({colors[a.featureIndex - 1]});"
                    >
                        {a.featureIndex}
                    </div>

                    {#if groupType == "radio"}
                        {@render radioLabel(a)}
                    {:else}
                        {@render checkboxLabel(a)}
                    {/if}
                </div>
            </li>
        {/each}
    </ul>
</div>

<style>
    ul {
        list-style-type: none;
        padding: 0;
    }
    li {
        display: flex;
        align-items: center;
        gap: 0.5em;
    }
    li:hover {
        background-color: rgba(100, 255, 255, 0.3);
    }
    div.feature-container {
        display: flex;
        align-items: center;
    }
    div.color-box {
        display: inline-block;
        width: 1.5em;
        height: 1.5em;
        border-radius: 0.75em;
        border: 1px solid rgba(0, 0, 0, 0.1);
        text-align: center;
        justify-content: center;
    }    
    label {
        display: flex;
        flex:1
    }
</style>
