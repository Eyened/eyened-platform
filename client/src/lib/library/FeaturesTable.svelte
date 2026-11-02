<script lang="ts">
    import { ApiError } from "$lib/api/client";
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { MultiSelect } from "$lib/components/ui/multi-select/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import { fetchFeatures } from "$lib/data/api";
    import {
        createFeature,
        deleteFeature,
        updateFeature,
    } from "$lib/data/helpers";
    import { features } from "$lib/data/stores.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext } from "svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import ArrowRight from "carbon-icons-svelte/lib/ArrowRight.svelte";
    import Edit from "carbon-icons-svelte/lib/Edit.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import type { FeatureGET } from "../../types/openapi_types";

    const globalContext = getContext<GlobalContext>("globalContext");

    const headingId = "library-heading";
    const descriptionId = $props.id();

    let search = $state("");
    const query = $derived(search.trim().toLowerCase());
    const sorted = $derived(
        [...features.values()].sort((a, b) => a.name.localeCompare(b.name)),
    );
    const visible = $derived(
        query
            ? sorted.filter((f) => f.name.toLowerCase().includes(query))
            : sorted,
    );

    // Create and Edit share one modal; `editing` is null when creating.
    let editing = $state<FeatureGET | null>(null);
    let formOpen = $state(false);
    let name = $state("");
    let subfeatureIds = $state<string[]>([]);
    let missing = $state(false);

    const options = $derived(
        sorted
            .filter((f) => f.id !== editing?.id)
            .map((f) => ({ value: String(f.id), label: f.name })),
    );

    function openForm(f: FeatureGET | null) {
        editing = f;
        name = f?.name ?? "";
        subfeatureIds = f?.subfeature_ids?.map(String) ?? [];
        missing = false;
        formOpen = true;
    }

    function save() {
        const trimmed = name.trim();
        if (!trimmed) {
            missing = true;
            return false;
        }
        // [] clears the links on edit; the server replaces them with the list it gets.
        const body = {
            name: trimmed,
            subfeature_ids: subfeatureIds.map(Number),
        };
        const saved = editing
            ? updateFeature(editing.id, body)
            : createFeature(body);
        // Save responses carry no segmentation count; reload the list with counts.
        return saved.then(() => fetchFeatures({ with_counts: true }));
    }

    let deleting = $state<FeatureGET | null>(null);
    let deleteOpen = $state(false);

    function openDelete(f: FeatureGET) {
        deleting = f;
        deleteOpen = true;
    }

    // The server decides; the client words its refusal with the count it already shows.
    function refusal(f: FeatureGET, e: unknown): Error {
        if (!(e instanceof ApiError))
            return e instanceof Error ? e : new Error(String(e));
        if (e.code === "FEATURE_HAS_SEGMENTATIONS") {
            const n = f.segmentation_count ?? 0;
            return new Error(
                n > 0
                    ? `Used by ${n} ${n === 1 ? "segmentation" : "segmentations"} in your projects. Remove those first.`
                    : "This feature is used by segmentations in projects you don't have access to, so it can't be deleted.",
            );
        }
        if (e.code === "FEATURE_IS_CHILD") {
            const parents = (e.detail as { parents?: string[] }).parents ?? [];
            return new Error(
                parents.length
                    ? `${e.message} Parent features: ${parents.join(", ")}.`
                    : e.message,
            );
        }
        return e;
    }

    function confirmDelete() {
        const f = deleting;
        if (!f) return false;
        return deleteFeature(f.id).catch((e: unknown) => {
            throw refusal(f, e);
        });
    }

    // The deleted row's button is gone, so focus goes to the page heading.
    function focusHeadingIfDeleted(event: Event) {
        if (deleting && !features.has(deleting.id)) {
            event.preventDefault();
            document.getElementById(headingId)?.focus();
        }
    }
</script>

<p id={descriptionId} class="mb-4 text-body-compact-01 text-text-secondary">
    Segmentation counts include only your projects.
</p>

<Table.Toolbar>
    <Table.ToolbarSearch
        labelText="Search features"
        placeholder="Search features"
        bind:value={search}
    />
    <Button size="lg" class="ms-auto" onclick={() => openForm(null)}>
        Create feature <Add />
    </Button>
</Table.Toolbar>

{#if visible.length === 0}
    <Empty.Root>
        <Empty.Header>
            {#if query}
                <Empty.Title>No features match “{search.trim()}”</Empty.Title>
                <Empty.Description
                    >Try a different search term.</Empty.Description
                >
            {:else}
                <Empty.Title>No features yet</Empty.Title>
            {/if}
        </Empty.Header>
    </Empty.Root>
{:else}
    <Table.Root aria-label="Features" aria-describedby={descriptionId}>
        <Table.Header>
            <Table.Row>
                <Table.Head>Name</Table.Head>
                <Table.Head>Subfeatures</Table.Head>
                <Table.Head>Segmentations</Table.Head>
                <Table.Head><span class="sr-only">Actions</span></Table.Head>
            </Table.Row>
        </Table.Header>
        <Table.Body>
            {#each visible as f (f.id)}
                <Table.Row>
                    <Table.Cell>{f.name}</Table.Cell>
                    <Table.Cell>
                        <span class="line-clamp-1">
                            {f.subfeatures.map((s) => s.name).join(", ") || "—"}
                        </span>
                    </Table.Cell>
                    <Table.Cell>{f.segmentation_count ?? 0}</Table.Cell>
                    <Table.Cell class="pe-2 text-end whitespace-nowrap">
                        <Button
                            variant="ghost"
                            aria-label="Open in browser: {f.name}"
                            href={globalContext.makeInstancesBrowserURL({
                                variable: "Segmentation Feature Name",
                                type: "default",
                                operator: "IN",
                                value: [f.name],
                            })}
                        >
                            Open in browser <ArrowRight />
                        </Button>
                        <Button
                            variant="ghost"
                            aria-label="Edit {f.name}"
                            onclick={() => openForm(f)}
                        >
                            Edit <Edit />
                        </Button>
                        <Button
                            variant="ghost"
                            aria-label="Delete {f.name}"
                            onclick={() => openDelete(f)}
                        >
                            Delete <TrashCan />
                        </Button>
                    </Table.Cell>
                </Table.Row>
            {/each}
        </Table.Body>
    </Table.Root>
{/if}

<Modal
    bind:open={formOpen}
    modalHeading={editing ? "Edit feature" : "Create feature"}
    modalLabel={editing?.name}
    primaryButtonText={editing ? "Save" : "Create feature"}
    primaryButtonLoadingDescription={editing ? "Saving…" : "Creating…"}
    successDescription={editing ? "Saved" : "Created"}
    errorTitle={editing
        ? "Feature could not be saved"
        : "Feature could not be created"}
    onsubmit={save}
>
    <div class="flex flex-col gap-6">
        <TextInput
            labelText="Name"
            bind:value={name}
            maxlength={60}
            invalidText={missing && !name.trim()
                ? "Enter a feature name"
                : undefined}
        />
        <MultiSelect
            titleText="Subfeatures (optional)"
            {options}
            bind:values={subfeatureIds}
            placeholder="Search features"
        />
    </div>
</Modal>

<Modal
    bind:open={deleteOpen}
    danger
    size="xs"
    modalHeading="Delete feature"
    modalLabel={deleting?.name}
    primaryButtonText="Delete"
    primaryButtonLoadingDescription="Deleting…"
    successDescription="Deleted"
    errorTitle="Feature could not be deleted"
    onsubmit={confirmDelete}
    onCloseAutoFocus={focusHeadingIfDeleted}
>
    <p>Deletes the feature. This can't be undone.</p>
</Modal>
