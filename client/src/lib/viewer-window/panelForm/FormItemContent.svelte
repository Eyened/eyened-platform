<script lang="ts">
    import { browser } from "$app/environment";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { FormAnnotationObject } from "$lib/data/objects.svelte";
    import type { FormAnnotationsRepo } from "$lib/data/repos.svelte";
    import SchemaForm from "$lib/forms/SchemaForm.svelte";
    import { getDefault, resolveRefs } from "$lib/forms/schemaType";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { onMount, setContext } from "svelte";

    interface Props {
        globalContext: GlobalContext;
        viewerContext: ViewerContext;
        form: FormAnnotationObject;
        formAnnotationRepo: FormAnnotationsRepo;
        canEdit: boolean;
    }
    let { form, formAnnotationRepo, viewerContext, canEdit, globalContext }: Props = $props();
    setContext("viewerContext", viewerContext);

    // Schema from repo'd store
    const schemaRow = $derived(globalContext.formSchemas.store[form.$.form_schema_id]);
    const schema = $derived(resolveRefs(schemaRow?.schema ?? {}));

    $effect(() => {
        console.log(schema);
    });

    let value: any = $state();
    let status = $state("loading");
    onMount(async () => {
        await globalContext.ensureFormSchemasLoaded();
        value = await formAnnotationRepo.getValue(Number(form.id));
        status = "ready";
        if (!value) value = getDefault(schema);
    });

    async function onchange() {
        if (!canEdit) return;
        if (value) {
            status = "saving";
            await formAnnotationRepo.setValue(Number(form.id), value);
            status = "synced";
        }
    }

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
    <span>{form.$.creator.name}</span>
    <span class={status}>{status}</span>
</div>
<div class="header">
    <table>
        <tbody>
            <tr>
                <td>Patient identifier</td>
                <td>{viewerContext.instance.patient.identifier}</td>
            </tr>
            <tr>
                <td>Study date</td>
                <td>{new Date(viewerContext.instance.study?.date ?? "").toLocaleDateString()}</td>
            </tr>
            <tr>
                <td>Instance identifier</td>
                <td>{form.$.image_instance_id}</td>
            </tr>
            <tr>
                <td>Laterality</td>
                <td>{viewerContext.instance.laterality === "L" ? "OS" : viewerContext.instance.laterality === "R" ? "OD" : "?"}</td>
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
            {vertical}
            {collapse}
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
