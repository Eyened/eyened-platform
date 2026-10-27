<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { TextArea } from "$lib/components/ui/text-area/index.js";
    import { timeAgo } from "$lib/utils";
    import Edit from "carbon-icons-svelte/lib/Edit.svelte";
    import type { TagMeta, TagType } from "../../types/openapi_types";
    import AddTag from "./AddTag.svelte";
    import { tagPopoverClass } from "./popover";

    // Read-only Carbon tags, all wrapping, then Edit tags: a popover listing each tag with its comment
    // (Edit comment, Remove) and a combo box to add one. Each action keeps the popover open with Inline
    // loading on its button; a failure shows an inline error notification there.
    let {
        tagType,
        tags: itemTags = [],
        tag: onTag,
        untag: onUntag,
        onUpdate,
    }: {
        tagType: TagType;
        tags?: TagMeta[];
        tag: (id: number) => Promise<unknown>;
        untag: (id: number) => Promise<unknown>;
        onUpdate: (id: number, comment?: string) => Promise<unknown>;
    } = $props();

    let open = $state(false);
    let creating = $state(false);
    let editing = $state<number | null>(null);
    let comment = $state("");
    let pending = $state<string | null>(null);
    let error = $state<{ title: string; subtitle: string } | null>(null);
    const applied = $derived(new Set(itemTags.map((t) => t.id)));

    function report(title: string, e: unknown) {
        error = { title, subtitle: e instanceof Error ? e.message : String(e) };
    }

    async function run(
        key: string,
        title: string,
        action: () => Promise<unknown>,
    ): Promise<boolean> {
        if (pending) return false;
        pending = key;
        error = null;
        try {
            await action();
            return true;
        } catch (e) {
            report(title, e);
            return false;
        } finally {
            pending = null;
        }
    }

    function startEdit(t: TagMeta) {
        editing = t.id;
        comment = t.comment ?? "";
        error = null;
    }

    async function saveComment(t: TagMeta) {
        const saved = await run(
            `comment-${t.id}`,
            "Could not save the comment",
            () => onUpdate(t.id, comment.trim() || undefined),
        );
        if (saved) editing = null;
    }
</script>

<div class="flex flex-wrap items-center gap-2">
    {#each itemTags as t (t.id)}
        <Tag>{t.name}</Tag>
    {/each}
    <Popover.Root
        bind:open
        onOpenChange={(o) => {
            if (o) return;
            creating = false;
            editing = null;
            error = null;
        }}
    >
        <Popover.Trigger>
            {#snippet child({ props })}
                <Button {...props} variant="ghost" size="sm">
                    Edit tags
                    <Edit aria-hidden="true" />
                </Button>
            {/snippet}
        </Popover.Trigger>
        <Popover.Content
            data-slot="tag-popover"
            role="dialog"
            align="start"
            aria-label="Edit tags"
            class={tagPopoverClass}
        >
            {#if !creating && itemTags.length > 0}
                <ul class="mb-4 flex flex-col">
                    {#each itemTags as t (t.id)}
                        <li
                            class="flex flex-col gap-1 border-b border-border-subtle-01 py-3 first:pt-0 in-dialog:border-border-subtle-02"
                        >
                            <p class="text-heading-compact-01">{t.name}</p>
                            {#if editing === t.id}
                                <TextArea
                                    labelText="Comment on {t.name}"
                                    rows={2}
                                    bind:value={comment}
                                />
                                <div class="mt-2 flex">
                                    <Button
                                        variant="secondary"
                                        size="sm"
                                        class="flex-1"
                                        onclick={() => (editing = null)}
                                    >
                                        Cancel
                                    </Button>
                                    <Button
                                        size="sm"
                                        class="flex-1"
                                        aria-disabled={pending !== null ||
                                            undefined}
                                        onclick={() => saveComment(t)}
                                    >
                                        {#if pending === `comment-${t.id}`}
                                            <InlineLoading
                                                class="text-inherit"
                                                status="active"
                                                description="Saving…"
                                            />
                                        {:else}
                                            Save
                                        {/if}
                                    </Button>
                                </div>
                            {:else}
                                {#if t.comment}
                                    <p class="text-body-01">{t.comment}</p>
                                {/if}
                                <p class="text-label-01 text-text-secondary">
                                    Tagged by {t.tagger.name} · {timeAgo(
                                        new Date(t.date),
                                    )}
                                </p>
                                <div class="flex">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        aria-label="Edit comment on {t.name}"
                                        onclick={() => startEdit(t)}
                                    >
                                        Edit comment
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        aria-label="Remove {t.name}"
                                        aria-disabled={pending !== null ||
                                            undefined}
                                        onclick={() =>
                                            run(
                                                `remove-${t.id}`,
                                                `Could not remove ${t.name}`,
                                                () => onUntag(t.id),
                                            )}
                                    >
                                        {#if pending === `remove-${t.id}`}
                                            <InlineLoading
                                                status="active"
                                                description="Removing…"
                                            />
                                        {:else}
                                            Remove
                                        {/if}
                                    </Button>
                                </div>
                            {/if}
                        </li>
                    {/each}
                </ul>
            {/if}
            <AddTag
                {tagType}
                {applied}
                titleText="Add a tag"
                bind:creating
                onadd={(t) =>
                    run("add", `Could not add ${t.name}`, () => onTag(t.id))}
                onerror={report}
            />
            {#if pending === "add"}
                <InlineLoading
                    class="mt-2"
                    status="active"
                    description="Adding…"
                />
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
</div>
