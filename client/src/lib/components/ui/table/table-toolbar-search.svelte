<script lang="ts">
    import { Search } from "$lib/components/ui/search/index.js";

    // Carbon persistent toolbar search (carbon-components-svelte ToolbarSearch) over ui/search: it grows in the toolbar, keeps today's look
    // without the field's bottom border, and a field with text keeps the hover colour, as in @carbon/styles data-table/action.
    let {
        labelText,
        placeholder,
        id,
        value = $bindable(""),
    }: {
        labelText: string;
        placeholder?: string;
        id?: string;
        value?: string;
    } = $props();
</script>

<Search
    {labelText}
    {placeholder}
    {id}
    bind:value
    class="flex-1 basis-40 [&_input]:border-b-0 [&_input:not(:placeholder-shown)]:bg-field-hover-01"
/>
