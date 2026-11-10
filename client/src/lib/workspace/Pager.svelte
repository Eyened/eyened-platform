<script lang="ts">
    import * as Table from "$lib/components/ui/table/index.js";
    import { getContext } from "svelte";
    import type { Workspace } from "./workspace.svelte";

    const workspace = getContext<Workspace>("workspace");
</script>

{#if workspace.showPager}
    <!-- The border sits outside the pager so its 32 px controls fit. -->
    <div class="border-t border-border-subtle-01">
        <Table.Pagination
            size="sm"
            page={workspace.page}
            pageSize={workspace.preset.count}
            totalItems={workspace.catalogue.length}
            rangeText={workspace.pagerText}
            backwardHint="Shift + Page Up"
            forwardHint="Shift + Page Down"
            onchange={({ page }) => workspace.turnPage(page)}
        />
    </div>
{/if}
