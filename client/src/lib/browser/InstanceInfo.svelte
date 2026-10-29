<script lang="ts">
    import * as StructuredList from "$lib/components/ui/structured-list/index.js";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import {
        tagInstance,
        untagInstance,
        updateTagInstance,
    } from "$lib/data/helpers";
    import { instances } from "$lib/data/stores.svelte";
    import Tagger from "$lib/tags/Tagger.svelte";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";

    let { instanceId }: { instanceId: string } = $props();

    // Reactive: updates when instance in store changes!
    const instance = $derived(instances.get(instanceId)!);
    const browserContext = getContext<BrowserContext | undefined>(
        "browserContext",
    );

    const flattenToDotPaths = (
        input: Record<string, unknown> | unknown[],
    ): Record<string, unknown> => {
        const out: Record<string, unknown> = {};

        const walk = (value: unknown, path: string): void => {
            if (Array.isArray(value)) {
                if (value.length === 0 && path) {
                    out[path] = [];
                    return;
                }
                value.forEach((item, idx) => {
                    const next = path ? `${path}.${idx}` : `${idx}`;
                    walk(item, next);
                });
            } else if (value !== null && typeof value === "object") {
                const entries = Object.entries(
                    value as Record<string, unknown>,
                );
                if (entries.length === 0 && path) {
                    out[path] = {};
                    return;
                }
                for (const [k, v] of entries) {
                    const next = path ? `${path}.${k}` : k;
                    walk(v, next);
                }
            } else {
                if (path) out[path] = value as unknown;
            }
        };

        walk(input, "");
        return out;
    };

    // v1's flat field list in API order; the response has no grouping (D13).
    const rows = $derived(Object.entries(flattenToDotPaths(instance)));
</script>

<Tagger
    tagType="ImageInstance"
    tags={instance.tags ?? []}
    tag={async (id) => {
        await tagInstance(instance, id);
        browserContext?.refreshSignatures();
    }}
    untag={(id) => untagInstance(instance, id)}
    onUpdate={(tagId, comment) =>
        updateTagInstance(instance.id, tagId, comment)}
/>
<div class="flex min-h-0 flex-1 gap-4 max-md:flex-col">
    <img
        src={getThumbUrl(instance, 540)}
        alt="Preview of image {instance.id}"
        class="object-contain object-top md:h-full md:w-3/5"
    />
    <!-- Scrolls on its own from md; a focusable region so keyboard users can scroll it (Carbon Modal). -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div
        class="md:w-2/5 md:overflow-y-auto"
        tabindex="0"
        role="region"
        aria-label="Image properties"
    >
        <StructuredList.Root condensed aria-label="Image properties">
            <StructuredList.Head>
                <StructuredList.Row head>
                    <StructuredList.Cell head>Property</StructuredList.Cell>
                    <StructuredList.Cell head>Value</StructuredList.Cell>
                </StructuredList.Row>
            </StructuredList.Head>
            <StructuredList.Body>
                {#each rows as [key, value] (key)}
                    <StructuredList.Row>
                        <StructuredList.Cell class="break-all">
                            {key}
                        </StructuredList.Cell>
                        <StructuredList.Cell class="break-all">
                            {#if value == null}
                                NULL
                            {:else if typeof value === "object"}
                                <pre
                                    class="whitespace-pre-wrap">{JSON.stringify(
                                        value,
                                        null,
                                        2,
                                    )}</pre>
                            {:else}
                                {value}
                            {/if}
                        </StructuredList.Cell>
                    </StructuredList.Row>
                {/each}
            </StructuredList.Body>
        </StructuredList.Root>
    </div>
</div>
