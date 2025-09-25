<script lang="ts">
    import { StudyObject } from "$lib/data/objects.svelte";
    import extensions from "$lib/extensions";
    import Icon from "$lib/gui/Icon.svelte";
    import Tagger from "$lib/tags/Tagger.svelte";
    import Eye from "./Eye.svelte";
    import StudyBlockForms from "./StudyBlockForms.svelte";

    interface Props {
        study: StudyObject;
        mode?: "full" | "overlay";
    }

    let { study, mode = "full" }: Props = $props();
    let collapse = $state(false);

    const age = study.$?.age

    // const context = {
    //     study,
    //     patient: study.patient,
    //     project: study.patient.project,
    // };
    const { additional_data_sources } = extensions.browser.study;
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main block p-[0.3em] flex flex-col border border-[rgb(181,188,206)] rounded-[2px] shadow-[0_6px_12px_rgba(149,157,165,0.2)] mb-4">
    <div class="header text-lg font-bold cursor-pointer items-center hover:bg-gray-300/50 flex" onclick={() => (collapse = !collapse)}>
        {#if !collapse}
            ▼
        {:else}
            ►
        {/if}
        <div class="date-age m-[0.1em] items-center flex">
            <div class="date text-base">
                <Icon icon="calendar" />
                {new Date(study.$?.date).toISOString().slice(0, 10)}
            </div>
            <div class="age m-[0.1em]">({age ? Math.round(age) : ''} years)</div>

            <div class="ml-4">
            <Tagger
                tagType="Study"
                tags={study.$.tags ?? []}
                tag={(id) => study.tag(id)}
                untag={(id) => study.untag(id)}/>
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
            <!-- <AdditionalDataSources {context} {additional_data_sources} /> -->
        {/if}
    </div>
</div>

<style>

</style>
