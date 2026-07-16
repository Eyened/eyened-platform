<script lang="ts">
    import { instances } from "$lib/data";
    import type { SeriesGET } from "../../types/openapi_types";
    import InstanceComponent from "./InstanceComponent.svelte";

    interface Props {
        series: SeriesGET;
        laterality: "L" | "R" | null;
        showSegmentationInfo?: boolean;
    }
    let { series, laterality, showSegmentationInfo = true }: Props = $props();

    const images =
        series.instance_ids
            ?.map((id) => instances.get(id))
            .filter((inst) => inst && inst.laterality == laterality)
            .filter(
                (inst): inst is NonNullable<typeof inst> => inst !== undefined,
            ) ?? [];
</script>

{#if images.length}
    <div
        class="series m-[0.1em] flex flex-[0_1_auto] flex-col rounded-[2px] border border-[var(--browser-border)] bg-[var(--browser-background)]"
    >
        <div class="items flex flex-1 flex-row flex-wrap gap-[0.3em]">
            {#each images as instance (instance.id)}
                <InstanceComponent {instance} {showSegmentationInfo} />
            {/each}
        </div>
    </div>
{/if}
