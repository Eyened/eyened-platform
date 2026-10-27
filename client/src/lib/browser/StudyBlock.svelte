<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { tagStudy, untagStudy, updateTagStudy } from "$lib/data/helpers";
    import extensions from "$lib/extensions";
    import Tagger from "$lib/tags/Tagger.svelte";
    import { cn } from "$lib/utils.js";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import { getContext } from "svelte";
    import type { StudyGET } from "../../types/openapi_types";
    import AdditionalDataSources from "./AdditionalDataSources.svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import Eye from "./Eye.svelte";
    import { eyeImages } from "./images";
    import StudyBlockForms from "./StudyBlockForms.svelte";

    let { study }: { study: StudyGET } = $props();

    const uid = $props.id();
    let expanded = $state(true);

    const globalContext = getContext<GlobalContext>("globalContext");
    const browserContext = getContext<BrowserContext | undefined>(
        "browserContext",
    );

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

    const sexAge = $derived(
        [study.patient.sex, study.age ? `${Math.round(study.age)} years` : ""]
            .filter(Boolean)
            .join(", "),
    );
    const meta = $derived(
        [
            study.project.name,
            sexAge,
            study.round != null ? `Round ${study.round}` : "",
            study.description ?? "",
            `Study ID ${study.id}`,
        ]
            .filter(Boolean)
            .join(" · "),
    );

    const right = $derived(eyeImages(study, "R"));
    const left = $derived(eyeImages(study, "L"));
    const unknown = $derived(eyeImages(study, null));

    const { additional_data_sources } = extensions.browser.study;
    const dataSourceContext = $derived({
        study,
        patient: study.patient,
        project: study.project,
    });

    const link =
        "text-link-primary hover:text-link-primary-hover hover:underline";
</script>

<!-- Carbon ExpandableTile, interactive: the chevron is its own button at the bottom right. -->
<section
    data-slot="study-block"
    aria-labelledby="{uid}-heading"
    class="relative bg-layer-01 p-4 pb-12 in-dialog:bg-layer-02"
>
    <h2
        id="{uid}-heading"
        class="flex flex-wrap gap-x-2 text-heading-compact-02"
    >
        <!-- eslint-disable svelte/no-navigation-without-resolve -- both URLs are built by globalContext.makeStudiesBrowserURL(), which calls resolve() internally -->
        {#if urlByPatient}
            <a href={urlByPatient} class={link}>{study.patient.identifier}</a>
        {:else}
            <span>{study.patient.identifier}</span>
        {/if}
        <a href={urlByDate} class={link}>{study.date}</a>
        <!-- eslint-enable svelte/no-navigation-without-resolve -->
    </h2>
    <p class="mt-1 text-label-01 text-text-secondary">{meta}</p>
    <div class="mt-4">
        <Tagger
            tagType="Study"
            tags={study.tags ?? []}
            tag={async (id) => {
                await tagStudy(study, id);
                browserContext?.refreshSignatures();
            }}
            untag={(id) => untagStudy(study, id)}
            onUpdate={(tagId, comment) =>
                updateTagStudy(study.id, tagId, comment)}
        />
    </div>
    <div
        id="{uid}-details"
        hidden={!expanded}
        class="mt-4 border-t border-border-subtle-01 pt-4 in-dialog:border-border-subtle-02"
    >
        <div class="flex max-md:flex-col">
            <Eye laterality="R" images={right} />
            <Eye laterality="L" images={left} />
            {#if unknown.length > 0}
                <Eye laterality={null} images={unknown} />
            {/if}
        </div>
        <StudyBlockForms {study} />
        <AdditionalDataSources
            context={dataSourceContext}
            {additional_data_sources}
        />
    </div>
    <button
        type="button"
        aria-expanded={expanded}
        aria-controls="{uid}-details"
        aria-label={expanded ? "Collapse study" : "Expand study"}
        class="absolute right-0 bottom-0 flex size-12 cursor-pointer items-center justify-center hover:bg-layer-hover-01 in-dialog:hover:bg-layer-hover-02"
        onclick={() => (expanded = !expanded)}
    >
        <ChevronDown
            aria-hidden="true"
            class={cn(
                "text-icon-primary transition-transform duration-110",
                expanded && "rotate-180",
            )}
        />
    </button>
</section>
