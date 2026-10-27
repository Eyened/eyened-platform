<script lang="ts">
    import { ComboBox } from "$lib/components/ui/combo-box/index.js";
    import { createTag } from "$lib/data/helpers";
    import { tags } from "$lib/data/stores.svelte";
    import type { TagType } from "../../types/openapi_types";
    import TagEditForm from "./TagEditForm.svelte";

    // Carbon ComboBox over this type's tags not yet applied. Its last option, Create "<text>", swaps
    // the popover content for the create form (`creating`, which the caller also reads).
    let {
        tagType,
        applied,
        titleText,
        creating = $bindable(false),
        onadd,
        onerror,
    }: {
        tagType: TagType;
        applied: Set<number>;
        titleText: string;
        creating?: boolean;
        onadd: (tag: { id: number; name: string }) => Promise<unknown>;
        onerror: (title: string, error: unknown) => void;
    } = $props();

    const CREATE = "create";
    let text = $state("");
    let newName = $state("");

    const ofType = $derived(
        tags.filter(
            (t) =>
                t.tag_type ===
                (tagType === "Annotation" ? "FormAnnotation" : tagType),
        ),
    );
    const items = $derived.by(() => {
        const q = text.trim().toLowerCase();
        const matches = ofType
            .filter(
                (t) => !applied.has(t.id) && t.name.toLowerCase().includes(q),
            )
            .map((t) => ({ id: String(t.id), text: t.name }));
        const exists = ofType.some((t) => t.name.toLowerCase() === q);
        return q && !exists
            ? [...matches, { id: CREATE, text: `Create "${text.trim()}"` }]
            : matches;
    });

    function select(id: string) {
        if (id === CREATE) {
            newName = text.trim();
            creating = true;
            return;
        }
        const tag = ofType.find((t) => String(t.id) === id);
        if (tag) onadd({ id: tag.id, name: tag.name });
    }

    async function create(p: { name: string; description: string }) {
        try {
            const tag = await createTag(p.name, tagType, p.description);
            creating = false;
            await onadd({ id: tag.id, name: tag.name });
        } catch (e) {
            onerror(`Could not create ${p.name}`, e);
            throw e; // TagEditForm keeps its fields
        }
    }
</script>

{#if creating}
    <TagEditForm
        {tagType}
        initTagName={newName}
        submitText="Create and add"
        add={create}
        oncancel={() => (creating = false)}
    />
{:else}
    <ComboBox {titleText} {items} bind:value={text} onselect={select} />
{/if}
