<script lang="ts" module>
    export const TYPE_ITEMS = [
        { id: "all", text: "All" },
        { id: "Study", text: "Study" },
        { id: "ImageInstance", text: "Image" },
        { id: "Segmentation", text: "Segmentation" },
        { id: "FormAnnotation", text: "Form annotation" },
    ];
</script>

<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import {
        SelectInput,
        SelectItem,
    } from "$lib/components/ui/select-input/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import type { ResolvedPathname } from "$app/types";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { createTag, deleteTag } from "$lib/data/helpers";
    import { tags } from "$lib/data/stores.svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import ArrowRight from "carbon-icons-svelte/lib/ArrowRight.svelte";
    import Filter from "carbon-icons-svelte/lib/Filter.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import { getContext } from "svelte";
    import type { TagGET, TagType } from "../../types/openapi_types";

    let {
        type,
        onselecttype,
    }: { type: string; onselecttype: (type: string) => void } = $props();

    const headingId = "library-heading";
    const TYPE_LABEL: Record<TagType, string> = {
        Study: "Study",
        ImageInstance: "Image",
        Annotation: "Annotation",
        Segmentation: "Segmentation",
        FormAnnotation: "Form annotation",
    };

    const globalContext = getContext<GlobalContext>("globalContext");

    // Search has no variable for legacy Annotation tags, so they get no link.
    const IMAGE_TAG_VARIABLE = {
        ImageInstance: "Image Tag Name",
        Segmentation: "Segmentation Tag Name",
        FormAnnotation: "Form Tag Name",
    } as const;

    function browserURL(t: TagGET): ResolvedPathname | undefined {
        if (t.tag_type === "Study") {
            return globalContext.makeStudiesBrowserURL({
                variable: "Study Tag Name",
                operator: "IN",
                value: [t.name],
            });
        }
        if (t.tag_type === "Annotation") return undefined;
        return globalContext.makeInstancesBrowserURL({
            variable: IMAGE_TAG_VARIABLE[t.tag_type],
            type: "default",
            operator: "IN",
            value: [t.name],
        });
    }

    let search = $state("");
    const query = $derived(search.trim().toLowerCase());
    const visible = $derived(
        [...tags.values()]
            .filter(
                (t) =>
                    (type === "all" || t.tag_type === type) &&
                    (!query ||
                        [t.name, t.description].some((s) =>
                            s?.toLowerCase().includes(query),
                        )),
            )
            .sort((a, b) => a.name.localeCompare(b.name)),
    );

    let createOpen = $state(false);
    let name = $state("");
    let description = $state("");
    let tagType = $state<string>("ImageInstance");
    let missing = $state(false);

    function openCreate() {
        name = "";
        description = "";
        tagType = type === "all" ? "ImageInstance" : type;
        missing = false;
        createOpen = true;
    }

    function create() {
        if (!name.trim()) {
            missing = true;
            return false;
        }
        return createTag(name.trim(), tagType as TagType, description);
    }

    let deleting = $state<TagGET | null>(null);
    let deleteOpen = $state(false);

    function openDelete(t: TagGET) {
        deleting = t;
        deleteOpen = true;
    }

    function confirmDelete() {
        return deleting ? deleteTag(deleting.id) : false;
    }

    // The deleted row's button is gone, so focus goes to the page heading.
    function focusHeadingIfDeleted(event: Event) {
        if (deleting && !tags.has(deleting.id)) {
            event.preventDefault();
            document.getElementById(headingId)?.focus();
        }
    }
</script>

{#snippet typeFilter(variant: "default" | "inline")}
    <Dropdown
        type={variant}
        labelText="Type"
        items={TYPE_ITEMS}
        selectedId={type}
        onselect={onselecttype}
    />
{/snippet}

<Table.Toolbar>
    <Table.ToolbarSearch
        labelText="Search tags"
        placeholder="Search tags"
        bind:value={search}
    />
    <div class="hidden h-full items-center ps-4 md:flex">
        {@render typeFilter("inline")}
    </div>
    <!-- Below md the filter moves behind a toolbar filter button (Carbon TableToolbarFilter). -->
    <Popover.Root>
        <Popover.Trigger>
            {#snippet child({ props })}
                <IconButton {...props} label="Filter" class="size-12 md:hidden">
                    <Filter />
                </IconButton>
            {/snippet}
        </Popover.Trigger>
        <Popover.Content
            align="start"
            sideOffset={0}
            aria-label="Filter"
            class="flex w-72 flex-col gap-6 rounded-none border-0 bg-layer-01 p-4 text-text-primary shadow-popover"
        >
            {@render typeFilter("default")}
        </Popover.Content>
    </Popover.Root>
    <Button size="lg" class="ms-auto" onclick={openCreate}>
        Create tag <Add />
    </Button>
</Table.Toolbar>

{#if visible.length === 0}
    <Empty.Root>
        <Empty.Header>
            {#if query}
                <Empty.Title>No tags match “{search.trim()}”</Empty.Title>
                <Empty.Description>
                    Try a different search term or type.
                </Empty.Description>
            {:else if type !== "all"}
                <Empty.Title>No tags of this type</Empty.Title>
                <Empty.Description>
                    Choose another type, or create a tag.
                </Empty.Description>
            {:else}
                <Empty.Title>No tags yet</Empty.Title>
            {/if}
        </Empty.Header>
    </Empty.Root>
{:else}
    <Table.Root aria-label="Tags">
        <Table.Header>
            <Table.Row>
                <Table.Head>Name</Table.Head>
                <Table.Head>Description</Table.Head>
                <Table.Head>Type</Table.Head>
                <Table.Head>Owner</Table.Head>
                <Table.Head><span class="sr-only">Actions</span></Table.Head>
            </Table.Row>
        </Table.Header>
        <Table.Body>
            {#each visible as t (t.id)}
                <Table.Row>
                    <Table.Cell>{t.name}</Table.Cell>
                    <Table.Cell>
                        <span class="line-clamp-1">{t.description || "—"}</span>
                    </Table.Cell>
                    <Table.Cell>{TYPE_LABEL[t.tag_type]}</Table.Cell>
                    <Table.Cell>{t.creator?.name ?? "—"}</Table.Cell>
                    <Table.Cell class="pe-2 text-end whitespace-nowrap">
                        {@const href = browserURL(t)}
                        {#if href}
                            <Button
                                variant="ghost"
                                aria-label="Open in browser: {t.name}"
                                {href}
                            >
                                Open in browser <ArrowRight />
                            </Button>
                        {/if}
                        <Button
                            variant="ghost"
                            aria-label="Delete {t.name}"
                            onclick={() => openDelete(t)}
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
    bind:open={createOpen}
    modalHeading="Create tag"
    primaryButtonText="Create tag"
    primaryButtonLoadingDescription="Creating…"
    successDescription="Created"
    errorTitle="Tag could not be created"
    onsubmit={create}
>
    <div class="flex flex-col gap-6">
        <TextInput
            labelText="Name"
            bind:value={name}
            maxlength={256}
            invalidText={missing && !name.trim()
                ? "Enter a tag name"
                : undefined}
        />
        <SelectInput labelText="Type" bind:value={tagType}>
            {#each TYPE_ITEMS.slice(1) as item (item.id)}
                <SelectItem value={item.id} text={item.text} />
            {/each}
        </SelectInput>
        <TextInput
            labelText="Description (optional)"
            bind:value={description}
            maxlength={256}
        />
    </div>
</Modal>

<Modal
    bind:open={deleteOpen}
    danger
    size="xs"
    modalHeading="Delete tag"
    modalLabel={deleting?.name}
    primaryButtonText="Delete"
    primaryButtonLoadingDescription="Deleting…"
    successDescription="Deleted"
    errorTitle="Tag could not be deleted"
    onsubmit={confirmDelete}
    onCloseAutoFocus={focusHeadingIfDeleted}
>
    <p>Deletes the tag. This can't be undone.</p>
</Modal>
