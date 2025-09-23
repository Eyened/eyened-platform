<script lang="ts">
    import { PanelIcon, Trash } from "$lib/viewer-window/icons/icons";
    import type { DeviceModel } from "$lib/datamodel/device.svelte";
    export interface Props {
        deviceModel: DeviceModel;
    }

    const { deviceModel }: Props = $props();

    function deleteDeviceModel(deviceModel: DeviceModel) {
        deviceModel.delete();
    }
    let manufacturer = $state(deviceModel.manufacturer);
    let model = $state(deviceModel.model);
    function updateDeviceModel() {
        deviceModel.update({ manufacturer, model });
    }
</script>

<li>
    <span>[{deviceModel.id}]</span>
    <span><input type="text" bind:value={manufacturer} /></span>
    <span><input type="text" bind:value={model} /></span>
    <button
        onclick={updateDeviceModel}
        disabled={manufacturer == deviceModel.manufacturer &&
            model == deviceModel.model}
    >
        Update
    </button>
    <PanelIcon
        onclick={() => deleteDeviceModel(deviceModel)}
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
