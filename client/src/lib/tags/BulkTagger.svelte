<script lang="ts">
    import { imageCount } from "$lib/browser/images";
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { DismissibleTag } from "$lib/components/ui/tag/index.js";
    import { tagInstance, untagInstance } from "$lib/data/helpers";
    import type { ImageGET, TagMeta } from "../../types/openapi_types";
    import AddTag from "./AddTag.svelte";
    import { tagPopoverClass } from "./popover";

    // The batch bar's Tag: the tags every selected image has, each removable after a confirm (a bulk
    // remove deletes comments the user can't see), and a tag to add to all. No comments in bulk (v1).
    let {
        instances,
        class: className,
    }: { instances: ImageGET[]; class?: string } = $props();

    let open = $state(false);
    let creating = $state(false);
    let confirming = $state<TagMeta | null>(null);
    let pending = $state<"add" | "remove" | null>(null);
    let error = $state<{ title: string; subtitle: string } | null>(null);

    const n = $derived(instances.length);
    const shared = $derived.by(() => {
        const [first, ...rest] = instances;
        if (!first) return [];
        return (first.tags ?? []).filter((t) =>
            rest.every((i) => i.tags?.some((u) => u.id === t.id)),
        );
    });
    const applied = $derived(new Set(shared.map((t) => t.id)));

    function report(title: string, e: unknown) {
        error = { title, subtitle: e instanceof Error ? e.message : String(e) };
    }

    // One request at a time, as v1.
    async function addToAll(tag: { id: number; name: string }) {
        if (pending) return;
        pending = "add";
        error = null;
        const targets = instances.filter(
            (i) => !i.tags?.some((t) => t.id === tag.id),
        );
        try {
            for (const inst of targets) await tagInstance(inst, tag.id);
        } catch (e) {
            report(`Could not add ${tag.name} to all images`, e);
        } finally {
            pending = null;
        }
    }

    async function removeFromAll(tag: TagMeta) {
        if (pending) return;
        pending = "remove";
        error = null;
        const targets = instances.filter((i) =>
            i.tags?.some((t) => t.id === tag.id),
        );
        try {
            for (const inst of targets) await untagInstance(inst, tag.id);
        } catch (e) {
            report(`Could not remove ${tag.name} from all images`, e);
        } finally {
            pending = null;
            confirming = null;
        }
    }
</script>

<Popover.Root
    bind:open
    onOpenChange={(o) => {
        if (o) return;
        creating = false;
        confirming = null;
        error = null;
    }}
>
    <Popover.Trigger>
        {#snippet child({ props })}
            <Button {...props} size="lg" class={className}>Tag</Button>
        {/snippet}
    </Popover.Trigger>
    <Popover.Content
        data-slot="tag-popover"
        role="dialog"
        align="end"
        aria-label="Tags on all {imageCount(n)}"
        class={tagPopoverClass}
    >
        {#if confirming}
            <p class="text-body-01">
                Remove {confirming.name} from {imageCount(n)}? Comments on it
                are deleted.
            </p>
            <div class="mt-4 flex">
                <Button
                    variant="secondary"
                    size="sm"
                    class="flex-1"
                    onclick={() => (confirming = null)}
                >
                    Cancel
                </Button>
                <Button
                    variant="destructive"
                    size="sm"
                    class="flex-1"
                    aria-disabled={pending !== null || undefined}
                    onclick={() => confirming && removeFromAll(confirming)}
                >
                    {#if pending === "remove"}
                        <InlineLoading
                            class="text-inherit"
                            status="active"
                            description="Removing…"
                        />
                    {:else}
                        Remove
                    {/if}
                </Button>
            </div>
        {:else}
            {#if !creating}
                <h3 class="text-heading-compact-01">
                    Tags on all {imageCount(n)}
                </h3>
                {#if shared.length > 0}
                    <div class="mt-2 mb-4 flex flex-wrap gap-2">
                        {#each shared as t (t.id)}
                            <DismissibleTag
                                text={t.name}
                                title="Remove {t.name} from all images"
                                ondismiss={() => (confirming = t)}
                            />
                        {/each}
                    </div>
                {:else}
                    <p class="mt-2 mb-4 text-body-01 text-text-secondary">
                        No shared tags
                    </p>
                {/if}
            {/if}
            <AddTag
                tagType="ImageInstance"
                {applied}
                titleText="Add a tag to all {imageCount(n)}"
                bind:creating
                onadd={addToAll}
                onerror={report}
            />
            {#if pending === "add"}
                <InlineLoading
                    class="mt-2"
                    status="active"
                    description="Adding…"
                />
            {/if}
        {/if}
        {#if error}
            <InlineNotification
                class="mt-4"
                title={error.title}
                subtitle={error.subtitle}
            />
        {/if}
    </Popover.Content>
</Popover.Root>
