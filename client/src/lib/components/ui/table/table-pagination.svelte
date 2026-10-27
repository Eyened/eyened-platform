<script lang="ts">
    import { cn } from "$lib/utils.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import * as NativeSelect from "$lib/components/ui/native-select/index.js";
    import CaretLeft from "carbon-icons-svelte/lib/CaretLeft.svelte";
    import CaretRight from "carbon-icons-svelte/lib/CaretRight.svelte";
    import { tick } from "svelte";

    // Carbon Pagination, size lg, directly below a data table (so no top border). Outside a table, pass a top border (class="border-t border-border-subtle-01 in-dialog:border-border-subtle-02"), as Carbon draws one. Prop names from
    // carbon-components-svelte; strings and focus moves from @carbon/react 1.118.0 Pagination;
    // values from @carbon/styles 1.117.0 pagination/_pagination.scss.
    const uid = $props.id();
    let {
        page,
        pageSize,
        pageSizes,
        totalItems,
        onchange,
        class: className,
    }: {
        page: number;
        pageSize: number;
        pageSizes: number[];
        totalItems: number;
        onchange: (detail: { page: number; pageSize: number }) => void;
        class?: string;
    } = $props();

    let root = $state<HTMLElement | null>(null);

    const totalPages = $derived(Math.max(1, Math.ceil(totalItems / pageSize)));
    const pagesText = $derived(
        `${totalPages} ${totalPages === 1 ? "page" : "pages"}`,
    );
    const first = $derived(Math.min((page - 1) * pageSize + 1, totalItems));
    const last = $derived(Math.min(page * pageSize, totalItems));
    const atStart = $derived(page <= 1);
    const atEnd = $derived(page >= totalPages);

    // The end buttons stay focusable (aria-disabled); as in Carbon React, reaching an end
    // moves focus to the other button.
    async function step(delta: -1 | 1) {
        if (delta < 0 ? atStart : atEnd) return;
        const next = page + delta;
        onchange({ page: next, pageSize });
        const target =
            next === totalPages ? "backward" : next === 1 ? "forward" : null;
        if (target) {
            await tick();
            root?.querySelector<HTMLElement>(
                `[data-pagination="${target}"]`,
            )?.focus();
        }
    }

    const select =
        "h-12 border-0 bg-transparent pe-9 hover:bg-layer-hover-01 in-dialog:hover:bg-layer-hover-02";
    const button =
        "size-12 border-s-border-subtle-01 hover:bg-layer-hover-01 in-dialog:border-s-border-subtle-02 in-dialog:hover:bg-layer-hover-02";
</script>

<div
    bind:this={root}
    class={cn(
        "@container flex h-12 items-center justify-between bg-layer-01 text-body-compact-01 in-dialog:bg-layer-02",
        className,
    )}
>
    <div class="flex h-full items-center ps-4">
        <label
            for="{uid}-size"
            class="whitespace-nowrap text-text-primary @max-[42rem]:hidden"
        >
            Items per page:
        </label>
        <div
            class="h-full border-e border-border-subtle-01 @max-[42rem]:hidden in-dialog:border-border-subtle-02"
        >
            <NativeSelect.Root
                id="{uid}-size"
                class={select}
                value={String(pageSize)}
                onchange={(e) =>
                    onchange({
                        page: 1,
                        pageSize: Number(e.currentTarget.value),
                    })}
            >
                {#each pageSizes as size (size)}
                    <NativeSelect.Option value={String(size)}>
                        {size}
                    </NativeSelect.Option>
                {/each}
            </NativeSelect.Root>
        </div>
        <span
            class="ms-4 whitespace-nowrap text-text-secondary @max-[42rem]:ms-0"
        >
            {first}–{last} of {totalItems} items
        </span>
    </div>
    <div
        class="flex h-full items-center border-s border-border-subtle-01 @max-[42rem]:border-s-0 in-dialog:border-border-subtle-02"
    >
        <label for="{uid}-page" class="sr-only">Page of {pagesText}</label>
        <div class="h-full @max-[42rem]:hidden">
            <NativeSelect.Root
                id="{uid}-page"
                class={select}
                value={String(page)}
                onchange={(e) =>
                    onchange({ page: Number(e.currentTarget.value), pageSize })}
            >
                {#each { length: totalPages }, i (i)}
                    <NativeSelect.Option value={String(i + 1)}>
                        {i + 1}
                    </NativeSelect.Option>
                {/each}
            </NativeSelect.Root>
        </div>
        <span
            class="me-4 whitespace-nowrap text-text-primary @max-[42rem]:hidden"
        >
            of {pagesText}
        </span>
        <IconButton
            label="Previous page"
            data-pagination="backward"
            class={button}
            aria-disabled={atStart || undefined}
            onclick={() => step(-1)}
        >
            <CaretLeft />
        </IconButton>
        <IconButton
            label="Next page"
            data-pagination="forward"
            class={button}
            aria-disabled={atEnd || undefined}
            onclick={() => step(1)}
        >
            <CaretRight />
        </IconButton>
    </div>
</div>
