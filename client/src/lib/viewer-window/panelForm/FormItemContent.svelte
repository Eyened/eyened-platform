<script lang="ts">
    import { browser } from "$app/environment";
    import { formAnnotations, formSchemas, instances, setFormAnnotationValue, tagFormAnnotation, untagFormAnnotation } from "$lib/data";
    import { updateTagFormAnnotation } from "$lib/data/helpers";
    import SchemaForm from "$lib/forms/SchemaForm.svelte";
    import { getDefault, resolveRefs, type JSONSchema } from "$lib/forms/schemaType";
    import { onMount } from "svelte";
    import * as Tooltip from "../../components/ui/tooltip";
    import Tagger from "../../tags/Tagger.svelte";

    interface Props {
        formId: number;
        canEdit: boolean;
    }
    let { formId,  canEdit }: Props = $props();
    
    const form = $derived(formAnnotations.get(formId)!);
    const instance = $derived(instances.get(form.image_instance_id!));
    const formSchema = $derived(formSchemas.get(form.form_schema_id)!);
    const schema = $derived(resolveRefs(formSchema.schema as JSONSchema));

    // Keep value as independent $state (not derived from form.form_data) to:
    // 1. Prevent reactivity loops when updating the store
    // 2. Allow future throttling/debouncing of save operations
    // Value initializes from form ONCE on mount, then becomes independent for editing
    let value: any = $state(undefined);
    let status = $state("loaded");
    let saveTimeout: ReturnType<typeof setTimeout> | null = null;
    
    onMount(() => {
        // Initialize value from form data once
        value = form.form_data || getDefault(schema);
        
        // Debug logging
        console.log('Form:', form);
        if (!instance) {
            console.error(`Instance ${form.image_instance_id} not found`);
        }
    });


    async function onchange() {
        if (!canEdit) return;
        if (value) {
            // Clear existing timeout
            if (saveTimeout) {
                clearTimeout(saveTimeout);
            }
            
            // Show "saving" status immediately for user feedback
            status = "saving";
            
            // Debounce: wait 500ms after last keystroke before saving
            saveTimeout = setTimeout(async () => {
                await setFormAnnotationValue(form.id, value);
                status = "synced";
                saveTimeout = null;
            }, 500);
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

<Tooltip.Provider>
<div class="header">
    <span>[{form.id}]</span>
    <Tagger tagType="FormAnnotation" tags={form.tags ?? []}
        tag={(id) => {tagFormAnnotation(form, id);}}
        untag={(id) => untagFormAnnotation(form, id)}
        onUpdate={(tagId, comment) => updateTagFormAnnotation(form.id, tagId, comment)}
    />
    <span>{form.creator?.name}</span>
    <span class={status}>{status}</span>
</div>
<div class="header">
    <table>
        <tbody>
            <tr>
                <td>Patient identifier</td>
                <td>{instance?.patient.identifier}</td>
            </tr>
            <tr>
                <td>Study date</td>
                <td>{new Date(instance?.study?.date ?? "").toLocaleDateString()}</td>
            </tr>
            <tr>
                <td>Instance identifier</td>
                <td>{form.image_instance_id}</td>
            </tr>
            <tr>
                <td>Laterality</td>
                <td>{instance?.laterality === "L" ? "OS" : instance?.laterality === "R" ? "OD" : "?"}</td>
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
</Tooltip.Provider>
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
