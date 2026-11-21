<!--
@component
Keys at the end of the options bar: a popover with a table of keys and what they do for each list. Opening leaves focus on Keys; Esc closes it.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import Keyboard from "carbon-icons-svelte/lib/Keyboard.svelte";
    import type { KeyRow } from "./registry";

    let {
        lists,
        iconOnly = false,
    }: {
        /** Each list's heading and rows, in order. */
        lists: { title: string; rows: readonly KeyRow[] }[];
        /** The keyboard icon alone, with a "Keys" tooltip. */
        iconOnly?: boolean;
    } = $props();

    const uid = $props.id();
    let open = $state(false);
</script>

<Popover.Root bind:open>
    <Popover.Trigger>
        {#snippet child({ props })}
            {#if iconOnly}
                <IconButton {...props} size="icon-xs" label="Keys"
                    ><Keyboard /></IconButton
                >
            {:else}
                <Button {...props} variant="ghost" size="sm"
                    ><Keyboard />Keys</Button
                >
            {/if}
        {/snippet}
    </Popover.Trigger>
    <!-- Carbon Popover: opening leaves focus on the trigger. -->
    <Popover.Content
        role="dialog"
        aria-label="Keys"
        align="end"
        class="flex w-auto max-w-96 flex-col gap-4"
        onOpenAutoFocus={(e) => e.preventDefault()}
    >
        {#each lists as list, i (list.title)}
            <div>
                <h2
                    id="{uid}-{i}"
                    class="pb-2 text-heading-compact-01 text-text-primary"
                >
                    {list.title}
                </h2>
                <table
                    aria-labelledby="{uid}-{i}"
                    class="w-full border-collapse text-body-compact-01"
                >
                    <thead>
                        <tr class="text-label-01 text-text-secondary">
                            <th
                                scope="col"
                                class="font-normal pe-4 pb-1 text-start"
                                >Keys</th
                            >
                            <th scope="col" class="font-normal pb-1 text-start"
                                >Action</th
                            >
                        </tr>
                    </thead>
                    <tbody>
                        {#each list.rows as row, j (j)}
                            <tr class="border-t border-border-subtle-01">
                                <td
                                    class="py-1 pe-4 align-top whitespace-nowrap"
                                    ><kbd class="font-sans">{row.keys}</kbd></td
                                >
                                <td class="py-1 text-text-primary"
                                    >{row.action}</td
                                >
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/each}
    </Popover.Content>
</Popover.Root>
