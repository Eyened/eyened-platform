<!--
@component
Info: the selected viewport's image, as label-over-value rows with a copy button on each value, then View all properties… and the patient's visits.
-->
<script lang="ts">
    import InstanceInfoDialog from "$lib/browser/InstanceInfoDialog.svelte";
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { copyToClipboard } from "$lib/utils/copyToClipboard";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
    import { getContext, onDestroy, tick } from "svelte";
    import type { ImageGET } from "../../types/openapi_types";
    import { ageAt, eyeLabel } from "./imageMeta";
    import VisitsList from "./VisitsList.svelte";
    import type { Workspace } from "./workspace.svelte";

    let {
        instanceFor,
        subtitle,
        shown,
    }: {
        instanceFor: (imageId: string) => ImageGET | null;
        /** The Layers subtitle: "Viewport 1 · …". */
        subtitle: string;
        /** Info is the shown left panel; Visits loads only then. */
        shown: boolean;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const imageId = $derived(
        workspace.slots[workspace.selected]?.imageId ?? null,
    );
    const image = $derived(imageId ? instanceFor(imageId) : null);

    const SEX = { F: "Female", M: "Male" } as const;
    const EYE = { OD: "OD (right)", OS: "OS (left)" } as const;
    // The birth date shows only behind View all properties…: graders need the age at the exam (AVG data minimisation).
    const rows = $derived.by(() => {
        if (!image) return [];
        const age = ageAt(image.patient.birth_date, image.study.date);
        const eye = eyeLabel(image.laterality);
        return [
            { label: "Public ID", value: image.id },
            { label: "Patient ID", value: image.patient.identifier },
            {
                label: "Sex",
                value: image.patient.sex ? SEX[image.patient.sex] : null,
            },
            {
                label: "Age at this visit",
                value: age === null ? null : String(age),
            },
            { label: "Visit date", value: image.study.date },
            { label: "Modality", value: image.modality ?? null },
            { label: "Eye", value: eye ? EYE[eye] : null },
            { label: "ETDRS field", value: image.etdrs_field ?? null },
            { label: "Manufacturer", value: image.device.manufacturer || null },
            { label: "Model", value: image.device.model || null },
            { label: "Scan mode", value: image.scan.mode || null },
        ];
    });

    /** The row copied in the last 2 s. */
    let copiedLabel: string | null = $state(null);
    let announcement = $state("");
    let copiedTimer: ReturnType<typeof setTimeout> | undefined;
    onDestroy(() => clearTimeout(copiedTimer));

    // Carbon CopyButton feedback for 2 s, also announced (WCAG 4.1.3).
    async function copy(label: string, value: string) {
        if (!(await copyToClipboard(value))) return;
        clearTimeout(copiedTimer);
        copiedLabel = label;
        // Blank the live region first, so a repeat copy is announced again.
        announcement = "";
        await tick();
        announcement = `${label} copied`;
        copiedTimer = setTimeout(() => {
            copiedLabel = null;
            announcement = "";
        }, 2000);
    }

    let dialogOpen = $state(false);
</script>

<div class="flex flex-col pb-4">
    <p class="px-4 pb-2 text-label-01 text-text-secondary">{subtitle}</p>
    {#if image}
        <dl>
            {#each rows as row (row.label)}
                <div class="border-t border-border-subtle-01 py-2 ps-4 pe-2">
                    <dt class="text-label-01 text-text-secondary">
                        {row.label}
                    </dt>
                    <dd class="flex items-start gap-1 text-body-compact-01">
                        <span
                            class="min-w-0 flex-1 break-all {row.value
                                ? 'text-text-primary'
                                : 'text-text-secondary'}"
                            >{row.value ?? "None"}</span
                        >
                        {#if row.value}
                            {@const value = row.value}
                            <IconButton
                                label="Copy {row.label}"
                                tooltip={copiedLabel === row.label
                                    ? "Copied"
                                    : undefined}
                                size="icon-xs"
                                closeOnClick={false}
                                onclick={() => copy(row.label, value)}
                            >
                                <Copy />
                            </IconButton>
                        {/if}
                    </dd>
                </div>
            {/each}
        </dl>
        <Button
            variant="ghost"
            size="sm"
            class="mx-2 mt-2 self-start"
            onclick={() => (dialogOpen = true)}>View all properties…</Button
        >
        <InstanceInfoDialog instanceId={image.id} bind:open={dialogOpen} />
        <VisitsList instance={image} active={shown} />
    {:else}
        <p class="px-4 text-body-compact-01 text-text-secondary">
            Select a viewport with an image to see its information.
        </p>
    {/if}
    <p class="sr-only" role="status">{announcement}</p>
</div>
