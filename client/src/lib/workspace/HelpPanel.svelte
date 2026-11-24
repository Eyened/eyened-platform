<!--
@component
Help: every key, in a fixed order (View, Measure, Draw, Place, Viewport, Images, layout and panels, Keyboard cursor).
Each time it opens, only the armed tool's group is open, scrolled to just under the search field. The search filters in place and counts what matches.
-->
<script lang="ts">
    import * as Accordion from "$lib/components/ui/accordion/index.js";
    import { Search } from "$lib/components/ui/search/index.js";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import { getContext, tick, untrack } from "svelte";
    import {
        armedSection,
        HELP_SECTIONS,
        searchHelp,
        type HelpSection,
    } from "./helpKeys";
    import type { KeyRow } from "./tools/registry";
    import type { Workspace } from "./workspace.svelte";

    let { shown }: { shown: boolean } = $props();

    const workspace = getContext<Workspace>("workspace");
    const uid = $props.id();
    const slug = (title: string) =>
        title.toLowerCase().replace(/[^a-z]+/g, "-");

    let query = $state("");
    const searching = $derived(query.trim() !== "");
    const result = $derived(searchHelp(query));
    const sections: readonly HelpSection[] = $derived(
        searching ? result.sections : HELP_SECTIONS,
    );
    /** Open sections outside a search; untouched while searching, so clearing the search brings them back. */
    let open: string[] = $state([]);
    /** While searching every section with a match starts open. */
    let searchOpen: string[] = $derived(result.sections.map((s) => s.title));

    const resultText = $derived(
        !searching
            ? ""
            : result.count === 0
              ? `No keys match "${query.trim()}". Clear the search to see all keys.`
              : `${result.count} ${result.count === 1 ? "result" : "results"}`,
    );
    // Announced once typing has stopped for 500 ms, so each keystroke isn't read out.
    let announced = $state("");
    $effect(() => {
        const text = resultText;
        const timer = setTimeout(() => (announced = text), 500);
        return () => clearTimeout(timer);
    });

    // Switching tools while Help is open changes nothing; only opening Help reads the armed tool.
    $effect(() => {
        if (!shown) return;
        const group = untrack(() =>
            armedSection(workspace.armedTool, pointArming.session !== null),
        );
        open = group ? [group] : [];
        if (group)
            void tick().then(() =>
                document
                    .getElementById(`${uid}-${slug(group)}`)
                    ?.scrollIntoView({ block: "start" }),
            );
    });
</script>

{#snippet keyRows(rows: readonly KeyRow[])}
    <dl
        class="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-label-01 text-text-secondary"
    >
        {#each rows as row (row.keys + row.action)}
            <dt><kbd class="font-sans text-text-primary">{row.keys}</kbd></dt>
            <dd>{row.action}</dd>
        {/each}
    </dl>
{/snippet}

<div class="flex flex-col pb-4">
    <div class="sticky top-0 z-1 bg-layer-01 px-4 pb-2">
        <!-- On the layer-01 panel the field takes the 02 tokens (Carbon's contextual field colours). -->
        <Search
            size="md"
            labelText="Search keys"
            placeholder="Search keys"
            class="[&_button:hover]:bg-field-hover-02 [&_input]:border-border-strong-02 [&_input]:bg-field-02 [&_input:hover]:bg-field-hover-02"
            bind:value={query}
        />
        {#if searching}
            <p class="pt-2 text-label-01 text-text-secondary">{resultText}</p>
        {/if}
    </div>
    <p class="sr-only" role="status">{announced}</p>
    <!-- Focus scrolls the focused title, so the margin sits on the titles too. -->
    <Accordion.Root
        class="[&_button]:scroll-mt-12"
        bind:value={
            () => (searching ? searchOpen : open),
            (v) => (searching ? (searchOpen = v) : (open = v))
        }
    >
        {#each sections as section (section.title)}
            <!-- scroll-mt keeps a scrolled-to section under the sticky search field. -->
            <Accordion.Item
                value={section.title}
                id="{uid}-{slug(section.title)}"
                class="scroll-mt-12"
            >
                <Accordion.Trigger level={3}>{section.title}</Accordion.Trigger>
                <Accordion.Content>
                    {#each section.tools as tool (tool.name)}
                        <div class="pb-3">
                            <p
                                class="flex items-baseline justify-between gap-2 text-body-compact-01 text-text-primary"
                            >
                                <span>{tool.name}</span>
                                {#if tool.key}
                                    <kbd class="font-sans">{tool.key}</kbd>
                                {:else}
                                    <span
                                        class="text-label-01 text-text-secondary"
                                        >no key</span
                                    >
                                {/if}
                            </p>
                            <p class="text-label-01 text-text-secondary">
                                {tool.does}
                            </p>
                            {#if tool.rows.length > 0}
                                {@render keyRows(tool.rows)}
                            {/if}
                        </div>
                    {/each}
                    {#if section.rows.length > 0}
                        {@render keyRows(section.rows)}
                    {/if}
                </Accordion.Content>
            </Accordion.Item>
        {/each}
    </Accordion.Root>
</div>
