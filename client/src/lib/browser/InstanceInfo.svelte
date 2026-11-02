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
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { copyToClipboard } from "$lib/utils/copyToClipboard";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
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

    const asText = (value: unknown): string =>
        typeof value === "object"
            ? JSON.stringify(value, null, 2)
            : String(value);

    // Carbon CopyButton feedback: "Copied!" for 2 s on the copied row.
    let copiedKey: string | null = $state(null);
    async function copy(key: string, value: unknown) {
        if (await copyToClipboard(asText(value))) copiedKey = key;
        setTimeout(() => {
            if (copiedKey === key) copiedKey = null;
        }, 2000);
    }
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
                            {:else}
                                <div
                                    class="flex items-start justify-between gap-2"
                                >
                                    {#if typeof value === "object"}
                                        <pre
                                            class="whitespace-pre-wrap">{asText(
                                                value,
                                            )}</pre>
                                    {:else}
                                        <span>{value}</span>
                                    {/if}
                                    <IconButton
                                        label={copiedKey === key
                                            ? "Copied!"
                                            : `Copy ${key}`}
                                        class="size-6 shrink-0"
                                        closeOnClick={false}
                                        onclick={() => copy(key, value)}
                                    >
                                        <Copy />
                                    </IconButton>
                                </div>
                            {/if}
                        </StructuredList.Cell>
                    </StructuredList.Row>
                {/each}
            </StructuredList.Body>
        </StructuredList.Root>
    </div>
</div>
