<script lang="ts">
    import { DeviceModel, Device } from "$lib/datamodel/device.svelte";
    import { data } from "$lib/datamodel/model";
    import DeviceRow from "./DeviceRow.svelte";

    const { deviceModels } = data;

    let manufacturer = $state("");
    let model = $state("");

    function createDeviceModel(event: Event) {
        event.preventDefault();
        DeviceModel.create({ manufacturer, model });
        manufacturer = "";
        model = "";
    }
</script>

<div class="main">
    <h1>Features</h1>
    <div class="new">
        <span>New Device model:</span>
        <form onsubmit={createDeviceModel}>
            <label
                >Manufacturer
                <input type="text" bind:value={manufacturer} />
            </label>
            <label
                >Model
                <input type="text" bind:value={model} />
            </label>
            <button type="submit">Create</button>
        </form>
    </div>
    <ul>
        {#each $deviceModels as deviceModel}
            <DeviceRow {deviceModel} />
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
    .new {
        flex-direction: row;
    }

    div.main {
        overflow-y: auto;
    }
</style>
