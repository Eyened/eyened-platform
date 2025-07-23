<script lang="ts">
    import { Feature } from "$lib/datamodel/feature.svelte";
    import { data } from "$lib/datamodel/model";
    import FeatureRow from "./FeatureRow.svelte";

    const { features } = data;

    let name = $state("");

    function createFeature(event: Event) {
        event.preventDefault();
        Feature.create({ name });
        name = "";
    }
</script>

<div class="main">
    <h1>Features</h1>
    <div class="new-feature">
        <span>New Feature:</span>
        <form onsubmit={createFeature}>
            <input type="text" bind:value={name} />
            <button type="submit">Create</button>
        </form>
    </div>
    <ul class="feature-list">
        {#each $features as feature}
            <FeatureRow {feature} />
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

    div.main {
        overflow-y: auto;
    }
</style>
