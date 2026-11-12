<script lang="ts">
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { RadioButton } from "$lib/components/ui/radio-button/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { cn } from "$lib/utils.js";
    import {
        getSegmentationKey,
        type Segmentation,
    } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
    import { representationLetter } from "$lib/viewer-window/panelSegmentation/segmentationUtils";
    import { getContext } from "svelte";

    // Carbon modal with a radio-select data table: the radio is the first column, the primary acts on the picked row.
    let {
        open = $bindable(false),
        modalHeading,
        modalLabel,
        primaryButtonText,
        primaryButtonLoadingDescription,
        successDescription,
        errorTitle,
        rows,
        currentId = null,
        emptyTitle,
        emptyDescription,
        onpick,
    }: {
        open?: boolean;
        modalHeading: string;
        modalLabel: string;
        primaryButtonText: string;
        primaryButtonLoadingDescription: string;
        successDescription: string;
        errorTitle: string;
        rows: Segmentation[];
        /** Tagged "Current", for the reference already set. */
        currentId?: number | null;
        emptyTitle: string;
        emptyDescription: string;
        onpick: (row: Segmentation) => unknown;
    } = $props();

    const uid = $props.id();
    const me = getContext<GlobalContext>("globalContext").user.id;
    let picked = $state<string | null>(null);
    const pickedRow = $derived(
        rows.find((s) => getSegmentationKey(s) === picked),
    );

    // A reopened picker starts with nothing picked.
    $effect(() => {
        if (!open) picked = null;
    });

    function author(s: Segmentation): string {
        if (s.annotation_type === "model_segmentation") return "AI";
        return s.creator.id === me ? "Mine" : s.creator.name;
    }
</script>

<Modal
    bind:open
    {modalHeading}
    {modalLabel}
    {primaryButtonText}
    {primaryButtonLoadingDescription}
    {successDescription}
    {errorTitle}
    primaryButtonDisabled={!pickedRow}
    hasScrollingContent
    onsubmit={() => (pickedRow ? Promise.resolve(onpick(pickedRow)) : false)}
>
    {#if rows.length === 0}
        <Empty.Root class="py-6">
            <Empty.Header>
                <Empty.Title>{emptyTitle}</Empty.Title>
                <Empty.Description>{emptyDescription}</Empty.Description>
            </Empty.Header>
        </Empty.Root>
    {:else}
        <Table.Root aria-label={modalHeading}>
            <Table.Header>
                <Table.Row>
                    <Table.Head class="w-12"
                        ><span class="sr-only">Pick</span></Table.Head
                    >
                    <Table.Head>Feature</Table.Head>
                    <Table.Head>Author</Table.Head>
                    <Table.Head>Type</Table.Head>
                    <Table.Head>ID</Table.Head>
                </Table.Row>
            </Table.Header>
            <Table.Body>
                {#each rows as s, i (getSegmentationKey(s))}
                    {@const key = getSegmentationKey(s)}
                    {@const isCurrent =
                        currentId !== null && s.id === currentId}
                    <!-- A click anywhere on the row picks it; the radio stays the keyboard and screen-reader control. -->
                    <Table.Row
                        class={cn(
                            "cursor-pointer",
                            picked === key &&
                                "bg-layer-selected-01 hover:bg-layer-selected-hover-01",
                        )}
                        onclick={() => (picked = key)}
                    >
                        <Table.Cell>
                            <RadioButton
                                name="{uid}-pick"
                                value={key}
                                hideLabel
                                labelText="{s.feature.name} [{s.id}]"
                                checked={picked === key}
                                onchange={() => (picked = key)}
                                primaryFocus={picked === null
                                    ? i === 0
                                    : picked === key}
                                describedBy={isCurrent
                                    ? `${uid}-current`
                                    : undefined}
                            />
                        </Table.Cell>
                        <Table.Cell>
                            {s.feature.name}
                            {#if isCurrent}
                                <span id="{uid}-current"
                                    ><Tag>Current</Tag></span
                                >
                            {/if}
                        </Table.Cell>
                        <Table.Cell>{author(s)}</Table.Cell>
                        <Table.Cell
                            >{representationLetter(
                                s.data_representation,
                            )}</Table.Cell
                        >
                        <Table.Cell class="tabular-nums">{s.id}</Table.Cell>
                    </Table.Row>
                {/each}
            </Table.Body>
        </Table.Root>
    {/if}
</Modal>
