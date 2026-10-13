<script lang="ts">
    import { afterNavigate } from "$app/navigation";
    import { page } from "$app/state";
    import Selection from "$lib/browser/Selection.svelte";
    import { Button } from "$lib/components/ui/button/index.js";
    import { ContentSwitcher } from "$lib/components/ui/content-switcher/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { onMount, setContext, tick } from "svelte";
    import AdvancedFilters from "./AdvancedFilters.svelte";
    import BrowserContent from "./BrowserContent.svelte";
    import {
        BrowserContext,
        SORT_COLUMNS,
        type Condition,
        type FilterMode,
        type QueryMode,
        type SortBy,
        type SortDirection,
    } from "./browserContext.svelte";
    import FilterShorcuts from "./FilterShorcuts.svelte";

    interface Props {
        // Optionally reuse an externally owned context (e.g. to read the
        // selection back out from an overlay wrapper).
        context?: BrowserContext;
        // Sync filter/pagination state to the page URL (landing page only).
        syncUrl?: boolean;
        // Layout/styling hint forwarded to BrowserContent.
        mode?: "full" | "overlay";
        // Seed conditions/selection when not driven by the URL.
        initialConditions?: Condition[];
        initialSelectedIds?: string[];
    }
    let {
        context,
        syncUrl = true,
        mode = "full",
        initialConditions,
        initialSelectedIds,
    }: Props = $props();
    const browserContext: BrowserContext = context ?? new BrowserContext();
    setContext("browserContext", browserContext);

    const SORT_TEXT: Record<SortBy, string> = {
        "Study Date": "Study date",
        "Patient Birthdate": "Patient birthdate",
        "Date Inserted": "Date added",
    };
    const sortItems = SORT_COLUMNS.flatMap((column) => [
        { id: `${column}|ASC`, text: `${SORT_TEXT[column]}, oldest first` },
        { id: `${column}|DESC`, text: `${SORT_TEXT[column]}, newest first` },
    ]);

    let patientInput = $state<HTMLInputElement | null>(null);

    const countText = $derived.by(() => {
        if (!browserContext.hasSearched || browserContext.failed) return "";
        if (browserContext.loading && browserContext.count === 0) return "";
        const n = browserContext.count;
        return browserContext.queryMode === "instances"
            ? `${n} ${n === 1 ? "image" : "images"}`
            : `${n} ${n === 1 ? "study" : "studies"}`;
    });

    onMount(async () => {
        browserContext.urlSync = syncUrl;
        await browserContext.loadSignatures();

        if (syncUrl) {
            const hasConditions = browserContext.restoreFromParams(
                page.url.searchParams,
            );
            if (mode === "full" && browserContext.filterMode === "basic") {
                await tick();
                patientInput?.focus();
            }
            // Only a URL with conditions searches; no params means no request (B9).
            if (hasConditions) await browserContext.search();
        } else {
            if (initialSelectedIds?.length) {
                browserContext.selectedIds = [...initialSelectedIds];
            }
            if (initialConditions?.length) {
                browserContext.applyInitialConditions(initialConditions, {
                    queryMode: "studies",
                    displayMode: "study",
                    filterMode: "advanced",
                });
                await browserContext.search();
            }
        }
    });

    // A patient or date link in a study header navigates this same route: read the URL again (B16).
    // Our own searches use goto (type "goto"); arriving from another route is onMount's job.
    afterNavigate((nav) => {
        if (!syncUrl || nav.type !== "link" || !nav.to) return;
        if (nav.from?.route.id !== nav.to.route.id) return;
        if (browserContext.restoreFromParams(nav.to.url.searchParams)) {
            browserContext.search();
        }
    });

    function submit(e: SubmitEvent) {
        e.preventDefault();
        // In the picker this form sits inside the modal's form; a bubbling submit would save.
        e.stopPropagation();
        if (browserContext.canSearch && !browserContext.loading) {
            browserContext.submitSearch();
        }
    }

    function selectSort(id: string) {
        const [by, direction] = id.split("|");
        browserContext.setSort(by as SortBy, direction as SortDirection);
    }
</script>

<div class="flex flex-col">
    {#if mode === "overlay" && browserContext.selectedIds.length > 0}
        <Selection placement="top" />
    {/if}
    {#if mode === "full"}
        <h1 tabindex="-1" class="mt-8 mb-6 text-heading-04 text-text-primary">
            Browser
        </h1>
    {/if}

    <form
        role="search"
        novalidate
        onsubmit={submit}
        class="flex flex-col gap-6"
    >
        <ContentSwitcher
            label="Filter mode"
            class="w-fit"
            items={[
                { id: "basic", text: "Basic" },
                { id: "advanced", text: "Advanced" },
            ]}
            selectedId={browserContext.filterMode}
            onchange={(id) => (browserContext.filterMode = id as FilterMode)}
        />
        {#if browserContext.filterMode === "basic"}
            <FilterShorcuts bind:patientInput />
        {:else}
            <AdvancedFilters />
        {/if}
        {#if browserContext.notification}
            {@const n = browserContext.notification}
            <InlineNotification
                kind={n.kind}
                title={n.title}
                subtitle={n.subtitle}
            />
        {/if}
        <div class="flex">
            <Button
                type="submit"
                aria-disabled={!browserContext.canSearch ||
                    browserContext.loading ||
                    undefined}
            >
                {#if browserContext.loading}
                    <InlineLoading
                        class="text-inherit"
                        status="active"
                        description="Searching…"
                    />
                {:else}
                    Search
                {/if}
            </Button>
            <Button
                variant="ghost"
                onclick={() => browserContext.clearFilters()}
            >
                Clear filters
            </Button>
        </div>
    </form>

    <!-- Carbon table-toolbar strip; below md it wraps to two lines. -->
    <Table.Toolbar class="mt-8 h-auto flex-wrap md:h-12">
        <p
            aria-live="polite"
            class="flex h-12 flex-1 items-center ps-4 text-body-compact-01 text-text-secondary"
        >
            {countText}
        </p>
        <div class="flex h-12 items-center gap-4">
            <!-- Manual: an arrow key moves focus without searching. -->
            <ContentSwitcher
                label="Results"
                size="lg"
                selectionMode="manual"
                class="w-fit"
                items={[
                    { id: "studies", text: "Studies" },
                    { id: "instances", text: "Images" },
                ]}
                selectedId={browserContext.queryMode}
                onchange={(id) =>
                    browserContext.resetForQueryModeChange(id as QueryMode)}
            />
            <Dropdown
                type="inline"
                labelText="Sort by"
                items={sortItems}
                selectedId={`${browserContext.sortBy}|${browserContext.sortDirection}`}
                onselect={selectSort}
            />
        </div>
    </Table.Toolbar>

    <BrowserContent {mode} />
    <footer></footer>
    {#if mode !== "overlay" && browserContext.selectedIds.length > 0}
        <Selection />
    {/if}
</div>

<style>
    footer {
        height: 200px;
    }
</style>
