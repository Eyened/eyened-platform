<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import extensions from "$lib/extensions";
    import Tagger from "$lib/tags/Tagger.svelte";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import Eye from "./Eye.svelte";

    import { tagStudy, untagStudy, updateTagStudy } from "$lib/data/helpers";
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
            : undefined,
    );

    const urlByDate = $derived(
        globalContext.makeStudiesBrowserURL({
            variable: "Study Date",
            operator: "==",
            value: study.date,
        }),
    );

    const { additional_data_sources } = extensions.browser.study;
    const dataSourceContext = {
        study,
        patient: study.patient,
        project: study.project,
    };
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="main mb-4 block flex flex-col rounded-[2px] border border-[rgb(181,188,206)] p-[0.3em] shadow-[0_6px_12px_rgba(149,157,165,0.2)]"
>
    <div
        class="header relative flex cursor-pointer items-center text-lg font-bold hover:bg-gray-300/50"
        onclick={() => (collapse = !collapse)}
    >
        <span
            class="absolute top-1 right-1 z-10 rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-600"
        >
            {study.id}
        </span>
        {#if !collapse}
            ▼
        {:else}
            ►
        {/if}
        <div class="date-age m-[0.1em] flex items-center">
            <div>
                <div class="text-base">
                    <span>{study.project.name}</span>
                    &nbsp;/&nbsp;
                    {#if urlByPatient}
                        <!-- eslint-disable svelte/no-navigation-without-resolve -- urlByPatient is built by globalContext.makeStudiesBrowserURL(), which calls resolve() internally; static analysis can't trace through the helper -->
                        <a
                            href={urlByPatient}
                            onclick={(e) => e.stopPropagation()}
                            class="hover:text-blue-600 hover:underline"
                        >
                            {study.patient.identifier}
                        </a>
                        <!-- eslint-enable svelte/no-navigation-without-resolve -->
                    {:else}
                        <span>{study.patient.identifier}</span>
                    {/if}
                    &nbsp;/&nbsp;
                    <!-- eslint-disable svelte/no-navigation-without-resolve -- urlByDate is built by globalContext.makeStudiesBrowserURL(), which calls resolve() internally; static analysis can't trace through the helper -->
                    <a
                        href={urlByDate}
                        onclick={(e) => e.stopPropagation()}
                        class="hover:text-blue-600 hover:underline"
                    >
                        {study.date}
                    </a>
                    <!-- eslint-enable svelte/no-navigation-without-resolve -->
                    <span class="ml-1">
                        [{study.patient.sex}
                        {study.age ? Math.round(study.age) : "?"} years]
                    </span>
                </div>
                {#if study.round !== undefined || study.description !== undefined}
                    <div class="info text-[12px]">
                        <span
                            class="z-10 rounded bg-gray-100 px-1.5 py-0.5 text-gray-600"
                        >
                            {#if study.round !== undefined}Round {study.round}
                            {/if}
                            {#if study.description !== undefined}{study.description}{/if}
                        </span>
                    </div>
                {/if}
            </div>

            <div class="ml-4">
                <Tagger
                    tagType="Study"
                    tags={study.tags ?? []}
                    tag={(id) => {
                        tagStudy(study, id);
                        browserContext?.refreshSignatures();
                    }}
                    untag={(id) => untagStudy(study, id)}
                    onUpdate={(tagId, comment) =>
                        updateTagStudy(study.id, tagId, comment)}
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
            <AdditionalDataSources
                context={dataSourceContext}
                {additional_data_sources}
            />
        {/if}
    </div>
</div>
