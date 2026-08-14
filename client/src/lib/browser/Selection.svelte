<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import { tagInstance, untagInstance } from "$lib/data/helpers";
    import Tagger from "$lib/tags/Tagger.svelte";
    import { getContext } from "svelte";
    import type { TagMeta } from "../../types/openapi_types";
    import InstanceComponent from "./InstanceComponent.svelte";
    import type { BrowserContext } from "./browserContext.svelte";

    const browserContext = getContext<BrowserContext>("browserContext");

    // 'bottom' (default) floats fixed at the bottom of the viewport (landing page).
    // 'top' sticks to the top of the scroll container (embedded overlay usage),
    // staying visible while taking up flow space so it never overlaps content.
    let { placement = "bottom" }: { placement?: "top" | "bottom" } = $props();

    const intersectionTagIds = $derived(
        (() => {
            const selected = browserContext.selectedInstances;
            if (selected.length === 0) return new Set<number>();

            let ids = new Set<number>(
                (selected[0].tags ?? []).map((t: TagMeta) => t.id),
            );
            for (let i = 1; i < selected.length; i++) {
                const current = new Set<number>(
                    (selected[i].tags ?? []).map((t: TagMeta) => t.id),
                );
                ids = new Set([...ids].filter((id) => current.has(id)));
                if (ids.size === 0) break;
            }
            return ids;
        })(),
    );

    const intersectionTags: TagMeta[] = $derived(
        (() => {
            const selected = browserContext.selectedInstances;
            if (selected.length === 0) return [];
            const ids = intersectionTagIds;
            return (selected[0].tags ?? []).filter((t: TagMeta) =>
                ids.has(t.id),
            );
        })(),
    );

    function clear() {
        browserContext.selectedIds = [];
    }

    function openSelectionTab() {
        browserContext.openTab(browserContext.selectedIds);
    }

    async function bulkTagSelection(tagId: number, comment?: string) {
        for (const inst of browserContext.selectedInstances) {
            const isAlreadyTagged = inst.tags?.some(
                (t: TagMeta) => t.id === tagId,
            );
            if (!isAlreadyTagged) {
                await tagInstance(inst, tagId, comment);
            }
        }
    }

    async function bulkUntagSelection(tagId: number) {
        for (const inst of browserContext.selectedInstances) {
            if (inst.tags?.some((t: TagMeta) => t.id === tagId)) {
                await untagInstance(inst, tagId);
            }
        }
    }
</script>

<div
    class="right-0 left-0 z-50 w-full bg-black/90 {placement === 'top'
        ? 'sticky top-0'
        : 'fixed bottom-0'}"
>
    <div class="flex items-start gap-4 p-2">
        <div class="button-container flex flex-col gap-1">
            <div>
                {browserContext.selectedIds.length}
                {browserContext.selectedIds.length != 1 ? "images" : "image"} selected
            </div>
            <Button
                variant="outline"
                disabled={browserContext.selectedIds.length === 0}
                onclick={openSelectionTab}
            >
                Open selected images
            </Button>
            <Button
                variant="outline"
                disabled={browserContext.selectedIds.length === 0}
                onclick={clear}
            >
                Clear selection
            </Button>

            <Tagger
                tagType="ImageInstance"
                tags={intersectionTags}
                tag={bulkTagSelection}
                untag={bulkUntagSelection}
            />
        </div>

        <div class="flex gap-2 overflow-x-auto">
            {#each browserContext.selectedInstances as instance (instance.id)}
                <InstanceComponent {instance} />
            {/each}
        </div>
    </div>
</div>
