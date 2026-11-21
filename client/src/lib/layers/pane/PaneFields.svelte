<!--
@component
A pane's label and value rows as a condensed structured list.
-->
<script lang="ts">
    import * as StructuredList from "$lib/components/ui/structured-list/index.js";

    let { rows }: { rows: [label: string, value: string][] } = $props();
</script>

<StructuredList.Root condensed>
    <StructuredList.Body>
        {#each rows as [label, value] (label)}
            <StructuredList.Row>
                <StructuredList.Cell>{label}</StructuredList.Cell>
                <StructuredList.Cell class="tabular-nums"
                    >{value}</StructuredList.Cell
                >
            </StructuredList.Row>
        {/each}
    </StructuredList.Body>
</StructuredList.Root>
