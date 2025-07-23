<script lang="ts">
    import { PanelIcon, Trash } from "$lib/viewer-window/icons/icons";
    import {
        AnnotationTypeFeature,
        type AnnotationType,
    } from "$lib/datamodel/annotationType.svelte";
    import { data } from "$lib/datamodel/model";
    import type { Feature } from "$lib/datamodel/feature.svelte";
    export interface Props {
        annotationType: AnnotationType;
    }

    const { annotationType }: Props = $props();
    const { features } = data;

    function deleteAnnotationType(annotationType: AnnotationType) {
        annotationType.delete();
    }
    let name = $state(annotationType.name);
    function updateAnnotationType() {
        annotationType.update({ name });
    }
    const { annotatedFeatures } = annotationType;
    function deleteFeature(annotationTypeFeature: AnnotationTypeFeature) {
        annotationTypeFeature.delete();
    }

    let baseFeatureId = $state<number | undefined>(annotationType.baseFeature?.id);
    $inspect(baseFeatureId);
    let selectedFeature = $state<Feature | undefined>(undefined);
    let selectedFeatureIndex = $state(1);
    function addFeature() {
        if (!selectedFeature) return;
        AnnotationTypeFeature.create({
            annotationTypeId: annotationType.id,
            featureId: selectedFeature.id,
            featureIndex: selectedFeatureIndex,
        });
        selectedFeatureIndex++;
    }
    async function updateBaseFeature() {
        if (baseFeatureId == undefined) return;
        const existing = data.annotationTypeFeatures
            .filter((f) => f.annotationTypeId == annotationType.id)
            .filter((f) => f.featureIndex == -1)
            .first();
        if (existing) {
            existing.delete();
        }
        const resp = await AnnotationTypeFeature.create({
            annotationTypeId: annotationType.id,
            featureId: baseFeatureId,
            featureIndex: -1,
        });
        
    }
</script>

<li class="main">
    <div>
        <span>[{annotationType.id}]</span>
        <span>{annotationType.dataRepresentation}</span>
        <span><input type="text" bind:value={name} /></span>
        <button
            onclick={updateAnnotationType}
            disabled={name == annotationType.name}>Update</button
        >
        <PanelIcon
            onclick={() => deleteAnnotationType(annotationType)}
            color="red"
            backgroundColor="white"
            Icon={Trash}
        />
    </div>
    {#if annotationType.dataRepresentation == "MultiLabel" || annotationType.dataRepresentation == "MultiClass"}
        <div class="features">
            <div>
                <span>Base Feature:</span>
                <select bind:value={baseFeatureId} onchange={updateBaseFeature}>
                    <option value="" selected disabled hidden>
                        Select main feature:
                    </option>
                    {#each $features as feature}
                        <option value={feature.id}>{feature.name}</option>
                    {/each}
                </select>
            </div>

            <ul>
                {#each $annotatedFeatures as annotatedFeature}
                    <li class="feature">
                        <span>[{annotatedFeature.featureIndex}]</span>
                        <span>{annotatedFeature.feature.name}</span>
                        <PanelIcon
                            onclick={() => deleteFeature(annotatedFeature)}
                            color="red"
                            backgroundColor="white"
                            Icon={Trash}
                        />
                    </li>
                {/each}
            </ul>
            <div class="feature-selector">
                <label>
                    Add Feature:
                    <select bind:value={selectedFeature}>
                        {#each $features as feature}
                            <option value={feature}>{feature.name}</option>
                        {/each}
                    </select>
                </label>
                <label>
                    Index:
                    <input type="number" bind:value={selectedFeatureIndex} />
                </label>
                <button onclick={addFeature} disabled={!selectedFeature}>
                    Add Feature
                </button>
            </div>
        </div>
    {/if}
</li>

<style>
    li.main {
        display: flex;
        flex-direction: column;
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 2px;
        padding: 0.5em;
    }
    li:hover {
        background-color: rgba(0, 0, 0, 0.1);
    }
    div {
        display: flex;
        flex-direction: row;
        align-items: center;
    }
    span {
        padding-left: 0.5em;
    }
    div.feature-selector {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
    }
    div.features {
        display: flex;
        align-items: flex-start;
        flex-direction: column;
    }
    li.feature {
        display: flex;
        flex-direction: row;
        align-items: flex-start;
    }
</style>
