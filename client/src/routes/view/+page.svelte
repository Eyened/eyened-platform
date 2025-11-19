<script lang="ts">
	import { browser } from "$app/environment";
	import { page } from "$app/state";
	import { fetchFormAnnotation, fetchSegmentation } from "$lib/data/api";
	import ViewerWindowLoader from "$lib/viewer-window/ViewerWindowLoader.svelte";

	function getURLNums(param: string): number[] {
		const params = browser ? page.url.searchParams : new URLSearchParams();
		return (
			params
				.get(param)
				?.split(",")
				.map((num) => parseInt(num))
				.filter((n) => !isNaN(n)) || []
		);
	}

	const urlInstanceIDs = getURLNums("instances");
	const urlFormAnnotationIDs = getURLNums("form_annotation_ids");
	const urlSegmentationIDs = getURLNums("segmentation_ids");
	const urlDeprecatedAnnotationIDs = getURLNums("annotations");

	async function resolveInstanceIDs(): Promise<number[]> {
		const ids = new Set<number>(urlInstanceIDs);

		// Resolve form annotation IDs to instance IDs
		for (const id of urlFormAnnotationIDs) {
			try {
				const fa = await fetchFormAnnotation(id);
				if (fa?.image_instance_id != null) {
					ids.add(fa.image_instance_id);
				}
			} catch (error) {
                console.error(error);                                
            }
		}

		// Resolve segmentation IDs to instance IDs
		for (const id of urlSegmentationIDs) {
			try {
				const seg = await fetchSegmentation(id);
				if (seg?.image_instance_id != null) {
					ids.add(seg.image_instance_id);
				}
			} catch (error) {
                console.error(error);
            }
		}

		// Handle deprecated annotation IDs (could be form annotations or segmentations)
		for (const id of urlDeprecatedAnnotationIDs) {
			let resolved = false;

			// Try as form annotation first
			try {
				const fa = await fetchFormAnnotation(id);
				if (fa?.image_instance_id != null) {
					ids.add(fa.image_instance_id);
					resolved = true;
				}
			} catch (error) {
                console.error(error);
            }

			// If not found as form annotation, try as segmentation
			if (!resolved) {
				try {
					const seg = await fetchSegmentation(id);
					if (seg?.image_instance_id != null) {
						ids.add(seg.image_instance_id);
					}
				} catch (error) {
                    console.error(error);
                }
			}
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
{:catch error}
	<div>Error: {error.message}</div>
{/await}
