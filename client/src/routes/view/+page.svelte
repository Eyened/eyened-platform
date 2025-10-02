<script lang="ts">
    import { browser } from "$app/environment";
    import { page } from "$app/state";
    import { FormAnnotationsRepo, SegmentationsRepo } from "$lib/data/repos.svelte";
    import ViewerWindowLoader from "$lib/viewer-window/ViewerWindowLoader.svelte";
    


    function getURLNums(param: string): number[] {
        const params = browser ? page.url.searchParams : new URLSearchParams();
        return params.get(param)?.split(",").map((num) => parseInt(num)).filter((n) => !isNaN(n)) || [];
    }

    const urlInstanceIDs = getURLNums("instances");
    const urlFormAnnotationIDs = getURLNums("form_annotation_ids");
    const urlSegmentationIDs = getURLNums("segmentation_ids");
    const urlDeprecatedAnnotationIDs = getURLNums("annotations");

    async function resolveInstanceIDs(): Promise<number[]> {
        const ids = new Set<number>(urlInstanceIDs);

        for (const id of urlFormAnnotationIDs) {
            try {
                const fa = await FormAnnotationsRepo.remoteGet(id);
                if ((fa as any)?.image_instance_id != null) ids.add((fa as any).image_instance_id as number);
            } catch {}
        }

        for (const id of urlDeprecatedAnnotationIDs) {
            let resolved = false;
            try {
                const fa = await FormAnnotationsRepo.remoteGet(id);
                if ((fa as any)?.image_instance_id != null) { ids.add((fa as any).image_instance_id as number); resolved = true; }
            } catch {}
            if (!resolved) {
                try {
                    const seg = await SegmentationsRepo.remoteGet(id);
                    if ((seg as any)?.image_instance_id != null) ids.add((seg as any).image_instance_id as number);
                } catch {}
            }
        }

        for (const id of urlSegmentationIDs) {
            try {
                const seg = await SegmentationsRepo.remoteGet(id);
                if ((seg as any)?.image_instance_id != null) ids.add((seg as any).image_instance_id as number);
            } catch {}
        }

        return Array.from(ids);
    }

    const instanceIDsPromise = resolveInstanceIDs();
</script>

<svelte:head>
    <title>Eyened viewer</title>
</svelte:head>
{#await instanceIDsPromise}
    <div>Loading:</div>
{:then instanceIDs}
    <ViewerWindowLoader {instanceIDs} />
    <!-- {#await Promise.all(
        instanceIDs.map((id) =>
            Instances.fetchOne(id, {
                with_segmentations: true,
                with_form_annotations: true,
                with_model_segmentations: true
            })
        )
    )}
        <div>Loading:</div>
    {:then _}
        <ViewerWindowLoader {instanceIDs} />
    {:catch error}
        <div>Error: {error.message}</div>
    {/await} -->
{:catch error}
    <div>Error: {error.message}</div>
{/await}
