<script lang="ts">
    import { cn } from "$lib/utils.js";
    import type { HTMLTableAttributes } from "svelte/elements";
    import Body from "./table-body.svelte";
    import Cell from "./table-cell.svelte";
    import Head from "./table-head.svelte";
    import Header from "./table-header.svelte";
    import Root from "./table.svelte";
    import Row from "./table-row.svelte";
    import Toolbar from "./table-toolbar.svelte";

    // Carbon DataTableSkeleton (@carbon/react 1.118.0); values from @carbon/styles 1.117.0
    // data-table/skeleton, utilities/_skeleton.scss and the button skeleton (150 px, sm 32 px).
    let {
        headers,
        rowCount = 5,
        size = "md",
        showToolbar = true,
        class: className,
        ...restProps
    }: HTMLTableAttributes & {
        headers: string[];
        rowCount?: number;
        size?: "md" | "xl";
        showToolbar?: boolean;
    } = $props();

    // Carbon's skeleton mixin: skeleton-background with an animated skeleton-element sweep.
    const skeleton =
        "relative block overflow-hidden bg-skeleton-background before:absolute before:inset-0 before:animate-skeleton before:bg-skeleton-element motion-reduce:before:animate-none";
</script>

{#if showToolbar}
    <Toolbar>
        <section
            aria-label="data table toolbar"
            class="flex h-full w-full justify-end"
        >
            <span class={cn(skeleton, "h-8 w-37.5 self-center")}></span>
        </section>
    </Toolbar>
{/if}
<Root {size} aria-busy="true" class={className} {...restProps}>
    <Header>
        <Row class="hover:bg-layer-01">
            {#each headers as header, i (i)}
                <Head>{header}</Head>
            {/each}
        </Row>
    </Header>
    <Body>
        {#each { length: rowCount }, r (r)}
            <Row class="hover:bg-layer-01">
                {#each headers as _, c (c)}
                    <Cell><span class={cn(skeleton, "h-4 w-16")}></span></Cell>
                {/each}
            </Row>
        {/each}
    </Body>
</Root>
