<script lang="ts">
    import * as Table from "$lib/components/ui/table/index.js";
    import { getContext } from "svelte";
    import type { Workspace } from "./workspace.svelte";

    const workspace = getContext<Workspace>("workspace");
</script>

{#if workspace.showPager}
    <Table.Pagination
        size="sm"
        class="border-t border-border-subtle-01"
        page={workspace.page}
        pageSize={workspace.preset.count}
        totalItems={workspace.catalogue.length}
        rangeText={workspace.pagerText}
        backwardHint="Shift + Page Up"
        forwardHint="Shift + Page Down"
        onchange={({ page }) => workspace.turnPage(page)}
    />
{/if}
