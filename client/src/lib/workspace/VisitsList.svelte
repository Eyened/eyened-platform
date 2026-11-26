<!--
@component
The selected image's patient's visits, newest first, each a Carbon Accordion item holding its data sources; this visit starts open.
It loads only while Info is shown; another patient's image reloads it with that image's visit open; another visit of the same patient opens that visit too.
-->
<script lang="ts">
    import AdditionalDataSources from "$lib/browser/AdditionalDataSources.svelte";
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import extensions from "$lib/extensions";
    import { untrack } from "svelte";
    import type { ImageGET } from "../../types/openapi_types";
    import {
        loadPatientStudies,
        PATIENT_STUDY_LIMIT,
        type PatientStudies,
    } from "./patientStudies";

    let { instance, active }: { instance: ImageGET; active: boolean } =
        $props();

    const { additional_data_sources } = extensions.viewer.panel_info;
    const identifier = $derived(instance.patient.identifier);
    const currentStudyId = $derived(instance.study.id);

    let loaded: { identifier: string; result: PatientStudies } | null =
        $state(null);
    let failed = $state(false);
    let open: string[] = $state([]);

    $effect(() => {
        if (!active) return;
        const id = identifier;
        if (untrack(() => loaded?.identifier) === id) return;
        const current = untrack(() => currentStudyId);
        let cancelled = false;
        failed = false;
        loadPatientStudies(id)
            .then((result) => {
                if (cancelled) return;
                loaded = { identifier: id, result };
                open = result.studies.some((s) => s.id === current)
                    ? [String(current)]
                    : [];
            })
            .catch(() => {
                // A failed load is dropped from the cache, so opening Info again retries it.
                if (!cancelled) failed = true;
            });
        return () => {
            cancelled = true;
        };
    });

    // Another visit of the same patient: open its item too; the grader's other items keep their state.
    $effect(() => {
        const id = String(currentStudyId);
        untrack(() => {
            if (loaded?.identifier !== identifier || open.includes(id)) return;
            if (loaded.result.studies.some((s) => String(s.id) === id))
                open = [...open, id];
        });
    });
</script>

<h3 class="px-4 pt-6 pb-2 text-heading-compact-01 text-text-primary">Visits</h3>
{#if failed}
    <!-- Never the patient ID or the URL. -->
    <div class="px-4">
        <InlineNotification
            title="Visits couldn't be loaded"
            subtitle="Try again later."
        />
    </div>
{:else if !loaded || loaded.identifier !== identifier}
    <!-- Not a live region: it would cut into the Info heading's announcement. -->
    <InlineLoading
        status="active"
        description="Loading visits…"
        live={false}
        class="px-4"
    />
{:else if loaded.result.studies.length === 0}
    <p class="px-4 text-body-compact-01 text-text-secondary">
        No visits found for this patient.
    </p>
{:else}
    <Accordion.Root bind:value={open}>
        {#each loaded.result.studies as study (study.id)}
            <Accordion.Item value={String(study.id)}>
                <!-- The project is the summary, which ends in an ellipsis, so a long name fits 256 px. -->
                <Accordion.Trigger level={4} summary={study.project.name}
                    >{study.date}{#if study.id === currentStudyId}
                        <Tag class="ms-2">This visit</Tag
                        >{/if}</Accordion.Trigger
                >
                <Accordion.Content>
                    <AdditionalDataSources
                        headingLevel={5}
                        context={{
                            study,
                            patient: study.patient,
                            project: study.project,
                        }}
                        {additional_data_sources}
                    />
                </Accordion.Content>
            </Accordion.Item>
        {/each}
    </Accordion.Root>
    {#if loaded.result.truncated}
        <p class="px-4 pt-2 text-label-01 text-text-secondary">
            Showing the {PATIENT_STUDY_LIMIT} most recent visits.
        </p>
    {/if}
{/if}
