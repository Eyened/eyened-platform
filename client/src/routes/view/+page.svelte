<script lang="ts">
	import { browser } from "$app/environment";
	import { page } from "$app/state";
	import { fetchFormAnnotation, fetchInstance, fetchSegmentation } from "$lib/data/api";
	import ViewerWindowLoader from "$lib/viewer-window/ViewerWindowLoader.svelte";

	function getURLStrings(param: string): string[] {
		const params = browser ? page.url.searchParams : new URLSearchParams();
		return (
			params
				.get(param)
				?.split(",")
				.map((value) => value.trim())
				.filter((value) => value.length > 0) || []
		);
	}

	const urlInstanceIDs = getURLStrings("instances");
	const urlFormAnnotationIDs = getURLStrings("form_annotation_ids");
	const urlSegmentationIDs = getURLStrings("segmentation_ids");
	const urlDeprecatedAnnotationIDs = getURLStrings("annotations");

	async function resolveInstanceIDs(): Promise<string[]> {
		const ids = new Set<string>();

		// Normalize URL-provided instance IDs to canonical public IDs.
		// This keeps temporary backwards compatibility for legacy numeric IDs.
		for (const id of urlInstanceIDs) {
			try {
				const instance = await fetchInstance(id);
				if (instance?.id) {
					ids.add(instance.id);
				}
			} catch (error) {
                console.error(error);
            }
		}

		// Resolve form annotation IDs to instance IDs
		for (const id of urlFormAnnotationIDs) {
			try {
				const fa = await fetchFormAnnotation(Number(id));
				if (fa?.image_id != null) {
					ids.add(fa.image_id);
				}
			} catch (error) {
                console.error(error);                                
            }
		}

		// Resolve segmentation IDs to instance IDs
		for (const id of urlSegmentationIDs) {
			try {
				const seg = await fetchSegmentation(Number(id));
				if (seg?.image_id != null) {
					ids.add(seg.image_id);
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
				const fa = await fetchFormAnnotation(Number(id));
				if (fa?.image_id != null) {
					ids.add(fa.image_id);
					resolved = true;
				}
			} catch (error) {
                console.error(error);
            }

			// If not found as form annotation, try as segmentation
			if (!resolved) {
				try {
					const seg = await fetchSegmentation(Number(id));
					if (seg?.image_id != null) {
						ids.add(seg.image_id);
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
