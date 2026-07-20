<script lang="ts">
    import type { ImageGET } from "../../types/openapi_types";

    interface Props {
        instance: ImageGET;
    }

    let { instance }: Props = $props();
    const segmentations = $derived(instance.segmentations ?? []);
</script>

<div id="main">
    {#if segmentations.length}
        <div>
            <h4>Segmentations:</h4>
            <table class="bg-white text-sm">
                <thead>
                    <tr>
                        <th
                            class="overflow-hidden px-[0.2em] text-left text-ellipsis whitespace-nowrap"
                            >ID</th
                        >
                        <th
                            class="overflow-hidden px-[0.2em] text-left text-ellipsis whitespace-nowrap"
                            >Creator</th
                        >
                        <th
                            class="overflow-hidden px-[0.2em] text-left text-ellipsis whitespace-nowrap"
                            >Feature</th
                        >
                    </tr>
                </thead>
                <tbody>
                    {#each segmentations as segmentation}
                        <tr>
                            <td
                                class="overflow-hidden px-[0.2em] text-left text-ellipsis whitespace-nowrap"
                                >{segmentation.id}</td
                            >
                            <td
                                class="overflow-hidden px-[0.2em] text-left text-ellipsis whitespace-nowrap"
                                >{segmentation.creator.name}</td
                            >
                            <td
                                class="overflow-hidden px-[0.2em] text-left text-ellipsis whitespace-nowrap"
                                >{segmentation.feature.name}</td
                            >
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    {/if}
</div>

<style>
</style>
