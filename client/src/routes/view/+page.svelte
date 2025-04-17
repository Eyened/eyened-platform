<script lang="ts">
    import ViewerWindowLoader from "$lib/viewer-window/ViewerWindowLoader.svelte";
    import { loadInstances } from "$lib/datamodel/api";
    import { page } from "$app/state";
    import { data } from "$lib/datamodel/model";
    import { browser } from "$app/environment";

    const { annotations } = data;
    // load instances and annotations from URL
    function getURLNums(param: string): number[] {
        const params = browser ? page.url.searchParams : new URLSearchParams();

        return (
            params
                .get(param)
                ?.split(",")
                .map((num) => parseInt(num)) || []
        );
    }
    const urlInstanceIDs = getURLNums("instances");
    const urlAnnotationIDs = getURLNums("annotations");

    // collect all instance IDs
    const instanceIDs = [
        ...new Set([
            ...urlInstanceIDs,
            ...urlAnnotationIDs
                .map((a) => annotations.get(a))
                .filter((a) => a && a.instance)
                .map((a) => a!.instance!.id),
        ]),
    ];
</script>

<svelte:head>
    <title>Eyened viewer</title>
</svelte:head>
{#await loadInstances(instanceIDs)}
    <div>Loading:</div>
{:then _}
    <ViewerWindowLoader {instanceIDs} />
{:catch error}
    <div>Error: {error.message}</div>
{/await}
