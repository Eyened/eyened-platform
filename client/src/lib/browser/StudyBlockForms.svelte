<script lang="ts">
    import type { Study } from "$lib/datamodel/study";    
    import StudyBlockForm from "./StudyBlockForm.svelte";
    import extensions from "$lib/extensions";
    interface Props {
        study: Study;
    }
    let { study }: Props = $props();
    const { list_forms } = extensions.browser.study;
</script>

{#each list_forms as { schema_name, split_laterality, title, create_new }}
    <StudyBlockForm
        {study}
        {schema_name}
        {split_laterality}
        {title}
        {create_new}
    />
{/each}
