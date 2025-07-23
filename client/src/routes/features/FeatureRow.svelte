<script lang="ts">
    import { PanelIcon, Trash } from "$lib/viewer-window/icons/icons";
    import type { Feature } from "$lib/datamodel/feature.svelte";
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
    <span>[{feature.id}]</span>
    <span><input type="text" bind:value={name} /></span>
    <button onclick={updateFeature} disabled={name == feature.name}
        >Update</button
    >
    <PanelIcon
        onclick={() => deleteFeature(feature)}
        color="red"
        backgroundColor="white"
    >
        <Trash />
    </PanelIcon>
</li>

<style>
    li {
        display: flex;
        padding-left: 0.5em;

        align-items: center;
    }
    li:hover {
        background-color: rgba(0, 0, 0, 0.1);
    }
    span {
        padding-left: 0.5em;
    }
</style>
