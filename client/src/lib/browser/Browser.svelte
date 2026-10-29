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
    import { cn } from "$lib/utils.js";
    import Filter from "carbon-icons-svelte/lib/Filter.svelte";
    import { onMount, setContext, tick, untrack } from "svelte";
    import AdvancedFilters from "./AdvancedFilters.svelte";
    import BrowserContent from "./BrowserContent.svelte";
    import {
        BrowserContext,
        SORT_COLUMNS,
        type Condition,
        type QueryMode,
        type SortBy,
        type SortDirection,
    } from "./browserContext.svelte";
    import FilterShorcuts from "./FilterShorcuts.svelte";
    import SelectedPanel from "./SelectedPanel.svelte";

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

    // The column overlays the results (Carbon slide-over side panel); not remembered.
    // Open on load only when no search starts, so it covers nothing.
    let filtersOpen = $state(
        untrack(
            () =>
                !(syncUrl
                    ? page.url.searchParams.get("conditions")
                    : initialConditions?.length),
        ),
    );
    let toggle = $state<HTMLButtonElement | null>(null);
    const filterCount = $derived(browserContext.activeConditions.length);
    let panelOpen = $state(false);

    // The panel closes when its last image is removed (or the selection is cleared).
    $effect(() => {
        if (browserContext.selectedIds.length === 0) panelOpen = false;
    });

    // Opening the panel closes the filter column.
    function viewSelected() {
        filtersOpen = false;
        panelOpen = !panelOpen;
    }

    // bits-ui returns focus to View selected; when the bar has gone, to Filters.
    function onPanelCloseAutoFocus(e: Event) {
        if (browserContext.selectedIds.length > 0) return;
        e.preventDefault();
        toggle?.focus();
    }

    // Notifications live in the column; open it so they are seen.
    $effect(() => {
        if (browserContext.notification) filtersOpen = true;
    });

    // Escape and Search close the open column.
    function closeOverlay() {
        filtersOpen = false;
        toggle?.focus();
    }

    function onFiltersKeydown(e: KeyboardEvent) {
        if (e.key !== "Escape") return;
        // A Select keeps focus on its trigger while open; let Escape close the menu first.
        if ((e.target as Element).closest('[aria-expanded="true"]')) return;
        // The picker's modal closes on Escape; its document listener skips a stopped event.
        e.stopPropagation();
        closeOverlay();
    }

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
        // Before any await: a Save while the fields load would otherwise unlink every image.
        if (!syncUrl && initialSelectedIds?.length) {
            browserContext.selectedIds = [...initialSelectedIds];
        }
        await browserContext.loadSignatures();

        if (syncUrl) {
            const hasConditions = browserContext.restoreFromParams(
                page.url.searchParams,
            );
            if (mode === "full" && filtersOpen) {
                await tick();
                patientInput?.focus();
            }
            // Only a URL with conditions searches; no params means no request (B9).
            if (hasConditions) await browserContext.search();
        } else {
            if (initialConditions?.length) {
                browserContext.applyInitialConditions(initialConditions, {
                    queryMode: "studies",
                    displayMode: "study",
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
            closeOverlay();
        }
    }

    function selectSort(id: string) {
        const [by, direction] = id.split("|");
        browserContext.setSort(by as SortBy, direction as SortDirection);
    }
</script>

<div class={cn("flex flex-col", mode === "full" && "pt-8")}>
    {#if mode === "full"}
        <h1 tabindex="-1" class="sr-only">Browser</h1>
    {/if}
    {#if browserContext.selectedIds.length > 0}
        <Selection {mode} {panelOpen} onviewselected={viewSelected} />
    {/if}
    <SelectedPanel
        bind:open={panelOpen}
        onCloseAutoFocus={onPanelCloseAutoFocus}
    />

    <!-- Carbon table-toolbar strip; it wraps when narrow. -->
    <Table.Toolbar class="h-auto min-h-12 flex-wrap">
        <Button
            bind:ref={toggle}
            variant="ghost"
            size="lg"
            aria-expanded={filtersOpen}
            aria-controls="browser-filters"
            onclick={() => (filtersOpen = !filtersOpen)}
        >
            {filtersOpen || filterCount === 0
                ? "Filters"
                : `Filters (${filterCount})`}
            <Filter aria-hidden="true" />
        </Button>
        {#if !filtersOpen && filterCount > 0}
            <Button
                variant="ghost"
                size="lg"
                onclick={() => {
                    browserContext.clearFilters();
                    toggle?.focus();
                }}
            >
                Clear filters
            </Button>
        {/if}
        <p
            aria-live="polite"
            class="flex h-12 flex-1 items-center ps-4 text-body-compact-01 text-text-secondary"
        >
            {countText}
        </p>
        <div class="flex min-h-12 flex-wrap items-center gap-x-4">
            <!-- Manual: an arrow key moves focus without searching. -->
            <ContentSwitcher
                label="Results"
                size="lg"
                selectionMode="manual"
                class="w-fit shrink-0"
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

    <!-- The column overlays the results, stacked in one grid cell so the container grows to fit
         the open column. -->
    <div class="relative grid grid-cols-1">
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <!-- Escape bubbles up from the fields inside this form. -->
        <form
            id="browser-filters"
            role="search"
            novalidate
            hidden={!filtersOpen}
            onsubmit={submit}
            onkeydown={onFiltersKeydown}
            class="z-30 col-start-1 row-start-1 flex w-full max-w-80 flex-col gap-6 self-start justify-self-start border-e border-border-subtle-00 bg-background px-4 py-6 in-dialog:border-border-subtle-01 in-dialog:bg-layer-01"
        >
            <h2 class="text-heading-compact-02 text-text-primary">Filters</h2>
            <FilterShorcuts bind:patientInput />
            <AdvancedFilters />
            {#if browserContext.notification}
                {@const n = browserContext.notification}
                <InlineNotification
                    kind={n.kind}
                    title={n.title}
                    subtitle={n.subtitle}
                />
            {/if}
            <div class="flex">
                <!-- In a dialog the dialog's own action is the one primary. -->
                <Button
                    type="submit"
                    variant={mode === "overlay" ? "secondary" : "default"}
                    aria-disabled={!browserContext.canSearch ||
                        browserContext.loading ||
                        undefined}
                >
                    Search
                    {#if browserContext.loading}
                        <InlineLoading
                            class="absolute inset-y-0 right-4 w-auto"
                            status="active"
                        />
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
        <!-- isolate keeps the results' own z-index layers under the batch bar (z-10), the scrim (z-20) and the column (z-30). -->
        <div class="isolate col-start-1 row-start-1 min-w-0">
            <BrowserContent />
        </div>
        <!-- Dims everything below the header under the open column; the picker's modal already dims the page. -->
        {#if mode === "full" && filtersOpen}
            <div
                aria-hidden="true"
                class="fixed inset-x-0 top-12 bottom-0 z-20 bg-overlay"
                onclick={closeOverlay}
            ></div>
        {/if}
    </div>
</div>
