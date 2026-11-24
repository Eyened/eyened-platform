<script module lang="ts">
    export const COMMENTS_ID = "set-comments";
</script>

<!--
@component
The set's comments: one line when empty, at most 5 lines unfocused, all of it while focused; saved 500 ms after typing stops and on blur.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { TextArea } from "$lib/components/ui/text-area/index.js";
    import type { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
    import { untrack } from "svelte";

    let {
        saver,
        initial,
        readonly = false,
    }: {
        saver: DebouncedSaver<string>;
        initial: string;
        /** I may not change this set's comments: still focusable and read. */
        readonly?: boolean;
    } = $props();

    let value = $state(untrack(() => initial));
    let focused = $state(false);
    // ASSUMPTION: rows follow the typed line breaks; a long paragraph scrolls inside.
    const lines = $derived(Math.max(value.split("\n").length, 1));
</script>

<div class="px-4 pb-3">
    <TextArea
        id={COMMENTS_ID}
        labelText="Comments"
        bind:value
        rows={focused ? lines : Math.min(lines, 5)}
        resize={false}
        {readonly}
        oninput={(e) => saver.edit(e.currentTarget.value)}
        onfocus={() => (focused = true)}
        onblur={() => {
            focused = false;
            void saver.flush();
        }}
        invalidText={saver.state === "error" ? "Couldn't save" : undefined}
    >
        {#snippet invalidAction()}
            <!-- Retry unmounts once the save works, so focus goes back to the field. -->
            <Button
                variant="ghost"
                size="sm"
                onclick={async () => {
                    await saver.flush();
                    document.getElementById(COMMENTS_ID)?.focus();
                }}>Retry</Button
            >
        {/snippet}
    </TextArea>
</div>
