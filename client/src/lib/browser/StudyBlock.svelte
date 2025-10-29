<script lang="ts">
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import extensions from "$lib/extensions";
	import Tagger from "$lib/tags/Tagger.svelte";
	import { getContext } from "svelte";
	import type { BrowserContext } from "./browserContext.svelte";
	import Eye from "./Eye.svelte";

	import { tagStudy, untagStudy } from "$lib/data/helpers";
	import type { StudyGET } from "../../types/openapi_types";
	import AdditionalDataSources from "./AdditionalDataSources.svelte";
	import StudyBlockForms from "./StudyBlockForms.svelte";
	interface Props {
		study: StudyGET;
		mode?: "full" | "overlay";
	}

	let { study, mode = "full" }: Props = $props();
	
	// Reactive: updates when study in store changes!
	// const study = $derived(studies.get(studyId)!);
	
	let collapse = $state(false);

	const globalContext = getContext<GlobalContext>("globalContext");
	const browserContext = getContext<BrowserContext>("browserContext");
	
	// Derived URLs for links
	const urlByPatient = $derived(
		study.patient.identifier
			? globalContext.makeStudiesBrowserURL({
					variable: "Patient Identifier",
					operator: "==",
					value: study.patient.identifier,
				})
			: ""
	);
	
	const dateStr = $derived(new Date(study.date).toISOString().slice(0, 10));
	const urlByDate = $derived(globalContext.makeStudiesBrowserURL({
		variable: "Study Date",
		operator: "==",
		value: dateStr,
	}));

	const { additional_data_sources } = extensions.browser.study;
	const dataSourceContext = {
        study,
        patient: study.patient,
        project: study.project,
    };
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="main block p-[0.3em] flex flex-col border border-[rgb(181,188,206)] rounded-[2px] shadow-[0_6px_12px_rgba(149,157,165,0.2)] mb-4"
>
	<div
		class="header text-lg font-bold cursor-pointer items-center hover:bg-gray-300/50 flex"
		onclick={() => (collapse = !collapse)}
	>
		{#if !collapse}
			▼
		{:else}
			►
		{/if}
		<div class="date-age m-[0.1em] items-center flex">
			<div class="date text-base">
				<span>{study.project.name}</span>
				&nbsp;/&nbsp;
				{#if urlByPatient}
					<a href={urlByPatient} onclick={(e) => e.stopPropagation()}>
						{study.patient.identifier}
					</a>
				{:else}
					<span>{study.patient.identifier}</span>
				{/if}
				&nbsp;/&nbsp;
				<a href={urlByDate} onclick={(e) => e.stopPropagation()}>
					{dateStr}
				</a>
				<span class="ml-1">({study.age ? Math.round(study.age) : ""} years)</span>
			</div>

			<div class="ml-4">
				<Tagger
					tagType="Study"
					tags={study.tags ?? []}
					tag={(id) => tagStudy(study, id)}
					untag={(id) => untagStudy(study, id)}
					onUpdate={browserContext.refreshSignatures}
				/>
			</div>
		</div>
	</div>
	<div class:hidden={collapse} class="flex flex-col">
		<div class="flex">
			<Eye laterality="R" {study} />
			<Eye laterality="L" {study} />
		</div>
		<Eye laterality={null} {study} />

		{#if mode == "full"}
			<StudyBlockForms {study} />
			<AdditionalDataSources context={dataSourceContext} {additional_data_sources} />
		{/if}
	</div>
</div>