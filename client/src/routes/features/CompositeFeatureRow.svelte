<script lang="ts">
    import { CompositeFeature } from "$lib/datamodel/compositeFeature.svelte";
    import type { Feature } from "$lib/datamodel/feature.svelte";
    import { data } from "$lib/datamodel/model";
    import { derived } from "svelte/store";

    export interface Props {
        feature: Feature;
    }

    const { feature }: Props = $props();

    const { features, compositeFeatures } = data;

    const linkedFeatures = compositeFeatures.filter(
        (cf) => cf.parentFeatureId == feature.id,
    );

    let selectedFeatureId: number | undefined = $state(undefined);
    let featureIndex: number = $state(0);
    linkedFeatures.subscribe((cfs) => {
        if (cfs.length == 0) {
            featureIndex = 1;
            return;
        }
        // set featureIndex to lowest unused index
        const usedIndices = new Set(cfs.map((cf) => cf.featureIndex));
        let i = 1;
        while (true) {
            if (!usedIndices.has(i)) {
                featureIndex = i;
                console.log(featureIndex);
                break;
            }
            i++;
        }
    });

    function addCompositeFeature(e: SubmitEvent) {
        e.preventDefault();
        if (selectedFeatureId) {
            CompositeFeature.create({
                parentFeatureId: feature.id,
                childFeatureId: selectedFeatureId,
                featureIndex,
            });
        }
    }
    let hasLinkedFeatures = derived(linkedFeatures, (cfs) => cfs.length > 0);
    let expanded = $state($hasLinkedFeatures);
</script>

<div>
    <button onclick={() => (expanded = !expanded)}>
        {#if $hasLinkedFeatures}
            Composite
        {/if}
        {#if expanded}
            -
        {:else}
            +
        {/if}
    </button>
</div>
<div class:collapsed={!expanded}>
    <ul>
        {#each $linkedFeatures as cf}
            <li>
                {cf.childFeature.name}
                <input
                    type="number"
                    min={1}
                    value={cf.featureIndex}
                    oninput={(e) => {
                        cf.update({
                            featureIndex: Number(
                                (e.target as HTMLInputElement).value,
                            ),
                        });
                    }}
                />
                <button onclick={() => cf.delete()}>Delete</button>
            </li>
        {/each}
    </ul>
    <div>
        <form onsubmit={addCompositeFeature}>
            <select bind:value={selectedFeatureId}>
                {#each $features as f}
                    <option value={f.id}>{f.name}</option>
                {/each}
            </select>
            [{featureIndex}]
            <button>Add</button>
        </form>
    </div>
</div>

<style>
    .collapsed {
        display: none;
    }
    input[type="number"] {
        width: 3ch;
    }
    li {
        display: grid;
        grid-template-columns: 1fr 0fr 0fr;
        gap: 0.5em;
    }
</style>
