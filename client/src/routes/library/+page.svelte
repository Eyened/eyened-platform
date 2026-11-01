<script lang="ts">
    import { goto } from "$app/navigation";
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import Main from "$lib/components/Main.svelte";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import * as Tabs from "$lib/components/ui/tabs/index.js";
    import { fetchFeatures, fetchTags } from "$lib/data/api";
    import FeaturesTable from "$lib/library/FeaturesTable.svelte";
    import TagsTable, { TYPE_ITEMS } from "$lib/library/TagsTable.svelte";

    const headingId = "library-heading";

    // Fetched here, not only at startup: the startup load swallows its errors and loads counts once.
    const tagsLoading = fetchTags();
    const featuresLoading = fetchFeatures({ with_counts: true });

    // Tab and type from the URL, read once.
    let tab = $state(
        page.url.searchParams.get("tab") === "features" ? "features" : "tags",
    );
    const urlType = page.url.searchParams.get("type");
    let type = $state(
        TYPE_ITEMS.some((i) => i.id === urlType) ? urlType! : "all",
    );

    function syncUrl() {
        // Built without mutation: svelte/prefer-svelte-reactivity flags a mutated URLSearchParams.
        const entries: [string, string][] = [];
        if (tab === "features") entries.push(["tab", "features"]);
        else if (type !== "all") entries.push(["type", type]);
        const qs = new URLSearchParams(entries).toString();
        goto(qs ? resolve(`/library?${qs}`) : resolve("/library"), {
            replaceState: true,
            keepFocus: true,
            noScroll: true,
        });
    }

    function errorText(error: unknown): string {
        return error instanceof Error ? error.message : String(error);
    }
</script>

<Main>
    <h1
        id={headingId}
        tabindex="-1"
        class="mt-8 mb-6 text-heading-04 text-text-primary"
    >
        Library
    </h1>

    <Tabs.Root
        bind:value={
            () => tab,
            (v) => {
                tab = v;
                syncUrl();
            }
        }
    >
        <Tabs.List aria-labelledby={headingId}>
            <Tabs.Trigger value="tags">Tags</Tabs.Trigger>
            <Tabs.Trigger value="features">Features</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="tags" class="pt-6">
            {#await tagsLoading}
                <Table.Skeleton
                    headers={["Name", "Description", "Type", "Owner"]}
                    aria-label="Tags"
                />
            {:then}
                <TagsTable
                    {type}
                    onselecttype={(v) => {
                        type = v;
                        syncUrl();
                    }}
                />
            {:catch error}
                <InlineNotification
                    title="Tags could not be loaded"
                    subtitle={errorText(error)}
                />
            {/await}
        </Tabs.Content>
        <Tabs.Content value="features" class="pt-6">
            {#await featuresLoading}
                <Table.Skeleton
                    headers={["Name", "Subfeatures", "Segmentations"]}
                    aria-label="Features"
                />
            {:then}
                <FeaturesTable />
            {:catch error}
                <InlineNotification
                    title="Features could not be loaded"
                    subtitle={errorText(error)}
                />
            {/await}
        </Tabs.Content>
    </Tabs.Root>
</Main>
