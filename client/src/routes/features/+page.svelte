<script lang="ts">
    import type { Feature } from "$lib/datamodel/feature";
    import { data } from "$lib/datamodel/model";
    import { PanelIcon, Trash } from "$lib/viewer-window/icons/icons";

    const { features } = data;

    function deleteFeature(feature: Feature) {
        features.delete(feature);
    }

    let featureName = $state("");

    function createFeature() {
        features.create({
            name: featureName,
        });
        featureName = "";
    }
</script>

<div class="main">
    <h1>Features</h1>
    <div class="new-feature">
        <span>New Feature:</span>
        <input type="text" bind:value={featureName} />
        <button onclick={createFeature}>Create</button>
    </div>
    <ul class="feature-list">
        {#each $features as feature}
            <li class="feature-row">
                <span>[{feature.id}]</span>
                <span>{feature.name}</span>

                <PanelIcon
                    onclick={() => deleteFeature(feature)}
                    color="red"
                    backgroundColor="white"
                >
                    <Trash />
                </PanelIcon>
            </li>
        {/each}
    </ul>
</div>

<style>
    div {
        display: flex;
    }
    .main {
        flex-direction: column;
        padding: 1em;
    }
    .new-feature {
        flex-direction: row;
    }
    li.feature-row {
        display: flex;
        padding-left: 0.5em;

        align-items: center;
    }
    .feature-row:hover {
        background-color: rgba(0, 0, 0, 0.1);
    }
    .feature-row span {
        padding-left: 0.5em;
    }
    div.main {
        overflow-y: auto;
    }
</style>
