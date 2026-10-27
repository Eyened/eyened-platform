<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import type { TagType } from "../../types/openapi_types";

    let {
        tagType,
        initTagName = "",
        initTagDescription = "",
        submitText = "Add",
        add,
        oncancel,
    }: {
        tagType: TagType;
        initTagName?: string;
        initTagDescription?: string;
        submitText?: string;
        add: (payload: {
            name: string;
            description: string;
            tagType: TagType;
        }) => void | Promise<unknown>;
        oncancel?: () => void;
    } = $props();

    let name = $state(initTagName);
    let description = $state(initTagDescription);
    let invalid = $state(false);
    let pending = $state(false);

    async function submit(e: SubmitEvent) {
        e.preventDefault();
        // In the picker an outer form would save.
        e.stopPropagation();
        if (pending) return;
        if (!name.trim()) {
            invalid = true;
            return;
        }
        pending = true;
        try {
            await add({ name: name.trim(), description, tagType });
            name = "";
            description = "";
        } catch {
            // The caller shows the error; the fields keep their text.
        } finally {
            pending = false;
        }
    }
</script>

<form class="flex flex-col gap-4" novalidate onsubmit={submit}>
    <TextInput
        labelText="Name"
        maxlength={256}
        bind:value={name}
        invalidText={invalid ? "Enter a tag name" : undefined}
        oninput={() => (invalid = false)}
    />
    <TextInput
        labelText="Description"
        maxlength={256}
        bind:value={description}
    />
    <div class="flex">
        {#if oncancel}
            <Button
                variant="secondary"
                size="sm"
                class="flex-1"
                onclick={oncancel}
            >
                Cancel
            </Button>
        {/if}
        <Button
            type="submit"
            size="sm"
            class="flex-1"
            aria-disabled={pending || undefined}
        >
            {#if pending}
                <InlineLoading
                    class="text-inherit"
                    status="active"
                    description="Creating…"
                />
            {:else}
                {submitText}
            {/if}
        </Button>
    </div>
</form>
