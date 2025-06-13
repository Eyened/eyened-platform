<script lang="ts">
    import SchemaForm from "$lib/forms/SchemaForm.svelte";
    import { getDefault, resolveRefs } from "$lib/forms/schemaType";
    import { onMount, setContext } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { FormAnnotation } from "$lib/datamodel/formAnnotation.svelte";
    import { browser } from "$app/environment";

    interface Props {
        form: FormAnnotation;
        viewerContext: ViewerContext;
        canEdit: boolean;
    }
    let { form, viewerContext, canEdit }: Props = $props();
    setContext("viewerContext", viewerContext);

    const schema = resolveRefs(form.formSchema.schema);

    let value: any = $state();
    let status = $state("loading");
    onMount(async () => {
        value = await form.value.load();
        status = "ready";
        if (!value) {
            value = getDefault(schema);
        }
    });

    async function onchange() {
        if (!canEdit) return;
        if (value) {
            status = "saving";
            await form.value.setValue(value);
            status = "synced";
        }
    }

    const laterality =
        form.instance?.laterality === "L"
            ? "OS"
            : form.instance?.laterality === "R"
              ? "OD"
              : "?";

    function readLocalStorageBoolean(key: string, defaultValue: boolean) {
        let value: string | null = null;
        if (browser) {
            value = localStorage.getItem(key);
        }
        if (value === null) {
            return defaultValue;
        }
        return value === "true";
    }
    let vertical = $state(
        readLocalStorageBoolean("form-item-content-vertical", true),
    );
    let collapse = $state(
        readLocalStorageBoolean("form-item-content-collapse", false),
    );

    $effect(() => {
        localStorage.setItem("form-item-content-vertical", vertical.toString());
    });
    $effect(() => {
        localStorage.setItem("form-item-content-collapse", collapse.toString());
    });
</script>

<div class="header">
    <span>[{form.id}]</span>
    <span>{form.creator.name}</span>
    <span class={status}>{status}</span>
</div>
<div class="header">
    <table>
        <tbody>
            <tr>
                <td>Patient identifier</td>
                <td> {form.patient.identifier}</td>
            </tr>
            <tr>
                <td>Study date</td>
                <td> {form.study?.date.toLocaleDateString()}</td>
            </tr>
            <tr>
                <td>Instance identifier</td>
                <td> {form.instance?.id}</td>
            </tr>
            <tr>
                <td>Laterality</td>
                <td> {laterality}</td>
            </tr>
        </tbody>
    </table>
</div>
<div class="header">
    <label>
        <span>Vertical:</span>
        <input type="checkbox" bind:checked={vertical} />
    </label>
    <label>
        <span>Collapse:</span>
        <input type="checkbox" bind:checked={collapse} />
    </label>
</div>
<div class="main">
    {#if value}
        <SchemaForm
            {schema}
            {value}
            {onchange}
            {canEdit}
            bind:vertical
            bind:collapse
        />
    {/if}
</div>

<style>
    div.header,
    div.main {
        padding: 0.5em;
    }
    div.main {
        display: flex;
        flex-direction: column;
        flex: 1;
        flex-direction: column;
        overflow: auto;
    }
    span.ready,
    span.synced {
        color: green;
    }
    span.saving {
        color: orange;
    }
    table {
        border-collapse: collapse;
        font-size: small;
    }
    td {
        padding: 0.2em;
    }
    tr:nth-child(odd) {
        background-color: rgba(0, 0, 0, 0.1);
    }
</style>
