<script lang="ts">
    import { PanelIcon, Trash } from "$lib/viewer-window/icons/icons";
    import type { Feature } from "$lib/datamodel/feature.svelte";
    import CompositeFeatureRow from "./CompositeFeatureRow.svelte";
    export interface Props {
        feature: Feature;
    }

    const { feature }: Props = $props();

    function deleteFeature(feature: Feature) {
        feature.delete();
    }
    let name = $state(feature.name);
    function updateFeature() {
        feature.update({ name });
    }
</script>

<li>
    <div>
        <span>[{feature.id}]</span>
        <form onsubmit={updateFeature}>
            <span><input type="text" bind:value={name} /></span>
            <button type="submit" disabled={name == feature.name}>
                Update
            </button>
        </form>
        <PanelIcon
            onclick={() => deleteFeature(feature)}
            color="red"
            backgroundColor="white"
            Icon={Trash}
        />
    </div>
    <div>
        <CompositeFeatureRow {feature} />
    </div>
</li>

<style>
    div {
        display: flex;
        flex-direction: row;
        align-items: center;
        
    }
    span {
        width: 3em;
        text-align: right;
    }
    li {
        display: flex;
        padding-left: 0.5em;
        
        flex-direction: column;
    }
    li:hover {
        background-color: rgba(0, 0, 0, 0.1);
    }
    span {
        padding-left: 0.5em;
    }
</style>
