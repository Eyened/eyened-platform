<script lang="ts">
    import type { GlobalContext } from '$lib/data/globalContext.svelte';
    import { StudyObject } from "$lib/data/objects.svelte";
    import extensions from "$lib/extensions";
    import Tagger from "$lib/tags/Tagger.svelte";
    import { getContext } from 'svelte';
    import Eye from "./Eye.svelte";
    import StudyBlockForms from "./StudyBlockForms.svelte";

    interface Props {
        study: StudyObject;
        mode?: "full" | "overlay";
    }

    let { study, mode = "full" }: Props = $props();
    let collapse = $state(false);

    const globalContext = getContext<GlobalContext>('globalContext');

    const age = study.$?.age

    const desc = study.$?.description ?? '(no name)';
    const patientId = study.$.patient.identifier;
    const dateStr = new Date(study.$?.date).toISOString().slice(0, 10);

    const urlByDesc = globalContext.makeStudiesBrowserURL({
        variable: 'Study Description',
        operator: '==',
        value: desc === '(no name)' ? '' : desc
    });

    const urlByPatient = patientId
        ? globalContext.makeStudiesBrowserURL({ variable: 'Patient Identifier', operator: '==', value: patientId })
        : '';

    const urlByDate = globalContext.makeStudiesBrowserURL({
        variable: 'Study Date',
        operator: '==',
        value: dateStr
    });

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
                <!-- <Icon icon="calendar" /> -->
                <span>{study.$.project.name}</span>
                &nbsp;/&nbsp;
                {#if urlByPatient}
                    <a href={urlByPatient} onclick={(e) => e.stopPropagation()}>{patientId}</a>
                {:else}
                    <span>{patientId}</span>
                {/if}
                &nbsp;/&nbsp;
                <a href={urlByDate} onclick={(e) => e.stopPropagation()}>{dateStr}</a>
                <span class="ml-1">({age ? Math.round(age) : ''} years)</span>
            </div>

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
