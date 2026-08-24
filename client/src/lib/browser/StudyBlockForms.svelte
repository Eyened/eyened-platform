<script lang="ts">
	import type { StudyGET, FormSchemaGET } from "../../types/openapi_types";
	import StudyBlockForm from "./StudyBlockForm.svelte";
	import extensions from "$lib/extensions";
	import { fetchFormAnnotations } from "$lib/data";
	import { formSchemas } from "$lib/data/stores.svelte";
	interface Props {
		study: StudyGET;
	}
	let { study }: Props = $props();

	// Fetch form annotations for this study
	const loading = fetchFormAnnotations({ study_id: study.id });

	const { list_forms } = extensions.browser.study;

	// Map list_forms to include the formSchema, filtering out those not found
	const formsWithSchemas = $derived(
		list_forms
			.map(({ schema_name, split_laterality, title, create_new }) => {
				const formSchema = formSchemas
					.values()
					.find((schema) => schema.name === schema_name);

				if (!formSchema) {
					console.error(`Form schema ${schema_name} not found`);
					return null;
				}

				return {
					formSchema,
					split_laterality,
					title,
					create_new,
				};
			})
			.filter((item): item is {
				formSchema: FormSchemaGET;
				split_laterality: boolean;
				title: string;
				create_new: boolean;
			} => item !== null),
	);
</script>

{#await loading then}
	{#each formsWithSchemas as { formSchema, split_laterality, title, create_new }}
		<StudyBlockForm
			{study}
			{split_laterality}
			{title}
			{create_new}
			{formSchema}
		/>
	{/each}
{/await}
