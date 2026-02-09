<script lang="ts">
	import { getContext } from "svelte";
	import type { SeriesGET, StudyGET } from "../../types/openapi_types";
	import type { BrowserContext } from "./browserContext.svelte";
	import SeriesComponent from "./SeriesComponent.svelte";
	import { Button } from "$lib/components/ui/button";
	import { instances } from "$lib/data";

	interface Props {
		study: StudyGET;
		laterality: "L" | "R" | null;
	}

	let { study, laterality }: Props = $props();

	const eye = laterality ? { L: "OS", R: "OD" }[laterality] : "OD/OS?";

	const browserContext = getContext<BrowserContext>("browserContext");

	function open() {
		const allInstanceIds =
			study.series?.flatMap((series) => series.instance_ids ?? []) ?? [];
		const allInstances = allInstanceIds.map((id) => instances.get(id));
		const eyeInstanceIds = allInstances
			.filter((instance) => instance?.laterality == laterality)
			.map((instance) => instance!.id);

		browserContext.openTab(eyeInstanceIds);
	}
	function hasLaterality(series: SeriesGET) {
		const images = series.instance_ids?.map((id) => instances.get(id));
		return images?.some((i) => i?.laterality == laterality);
	}

	const eyeSeries = study.series?.filter(hasLaterality) ?? [];
</script>

{#if eyeSeries?.length > 0}
	<div class="outer flex flex-1 flex-col p-2">
		<h3 class="m-0 text-base flex items-center gap-4">
			{eye}
			{#if eyeSeries?.length > 0}
				<Button variant="outline" onclick={open}>
					Open all {eye} images
				</Button>
			{/if}
		</h3>
		<div class="series-container flex flex-row flex-wrap content-start flex-1">
			{#each eyeSeries as series (series.id)}
				<SeriesComponent {series} {laterality} />
			{/each}
		</div>
	</div>
{/if}
