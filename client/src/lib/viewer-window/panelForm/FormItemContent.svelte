<script lang="ts">
    import { browser } from "$app/environment";
    import {
        formSchemas,
        instances,
        patients,
        setFormAnnotationValue,
        studies,
        tagFormAnnotation,
        untagFormAnnotation,
    } from "$lib/data";
    import { updateTagFormAnnotation } from "$lib/data/helpers";
    import SchemaForm from "$lib/forms/SchemaForm.svelte";
    import {
        getDefault,
        resolveRefs,
        type JSONSchema,
    } from "$lib/forms/schemaType";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { onMount, setContext } from "svelte";
    import * as Tooltip from "../../components/ui/tooltip";
    import Tagger from "../../tags/Tagger.svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";

    interface Props {
        form: FormAnnotationGET;
        canEdit: boolean;
        viewerContext?: ViewerContext;
    }
    let { form, canEdit, viewerContext }: Props = $props();

    if (viewerContext) {
        setContext("viewerContext", viewerContext);
    }
    setContext("pointFormAnnotationId", form.id);
    if (form.image_id) {
        setContext("pointBoundImageId", form.image_id);
    }

    const formSchema = $derived(formSchemas.get(form.form_schema_id)!);
    const schema = $derived(resolveRefs(formSchema.schema as JSONSchema));

    const instance = $derived(
        form.image_id ? instances.get(form.image_id) : undefined,
    );
    const patient = $derived(
        instance?.patient ?? patients.get(form.patient_id),
    );
    const study = $derived(
        instance?.study ??
            (form.study_id != null ? studies.get(form.study_id) : undefined),
    );

    function lateralityLabel(laterality: FormAnnotationGET["laterality"]) {
        if (laterality === "L") return "OS";
        if (laterality === "R") return "OD";
        return "N/A";
    }

    // Keep value as independent $state (not derived from form.form_data) to:
    // 1. Prevent reactivity loops when updating the store
    // 2. Allow future throttling/debouncing of save operations
    // Value initializes from form ONCE on mount, then becomes independent for editing
    let value: any = $state(undefined);
    let status = $state("loading");
    let saveTimeout: ReturnType<typeof setTimeout> | null = null;

    onMount(() => {
        // Initialize value from form data once
        value = form.form_data || getDefault(schema);
        status = "loaded";
    });

    async function onchange(next: unknown) {
        if (!canEdit) return;
        // Always apply `next`, including undefined/null/''/0/false. Callers use
        // undefined to omit/clear (PointField Remove, bare-single Clear, SchemaForm
        // trash). Treating undefined as "no change" left stale value in state and
        // the truthy save guard then wrote the old points back as a "successful" save.
        value = next;

        if (saveTimeout) {
            clearTimeout(saveTimeout);
        }

        // Show "saving" status immediately for user feedback
        status = "saving";

        // Debounce: wait 500ms after last keystroke before saving.
        // JSON body cannot be undefined — persist null for an omitted root value.
        saveTimeout = setTimeout(async () => {
            await setFormAnnotationValue(form.id, value ?? null);
            status = "synced";
            saveTimeout = null;
        }, 500);
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
        <Tagger
            tagType="FormAnnotation"
            tags={form.tags ?? []}
            tag={(id) => {
                tagFormAnnotation(form, id);
            }}
            untag={(id) => untagFormAnnotation(form, id)}
            onUpdate={(tagId, comment) =>
                updateTagFormAnnotation(form.id, tagId, comment)}
        />
        <span>{form.creator?.name}</span>
        <span class={status}>{status}</span>
    </div>
    <div class="header">
        <table>
            <tbody>
                <tr>
                    <td>Patient identifier</td>
                    <td>{patient?.identifier ?? "—"}</td>
                </tr>
                {#if study?.date}
                    <tr>
                        <td>Study date</td>
                        <td>{new Date(study.date).toLocaleDateString()}</td>
                    </tr>
                {/if}
                {#if form.image_id}
                    <tr>
                        <td>Image ID</td>
                        <td>{form.image_id}</td>
                    </tr>
                {/if}
                {#if form.laterality != null}
                    <tr>
                        <td>Laterality</td>
                        <td>{lateralityLabel(form.laterality)}</td>
                    </tr>
                {/if}
                {#if instance?.modality}
                    <tr>
                        <td>Modality</td>
                        <td>{instance.modality}</td>
                    </tr>
                {/if}
                {#if instance?.device?.manufacturer}
                    <tr>
                        <td>Manufacturer</td>
                        <td>{instance.device.manufacturer}</td>
                    </tr>
                {/if}
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
        {#if status !== "loading"}
            <SchemaForm
                {schema}
                {value}
                {onchange}
                {canEdit}
                {vertical}
                {collapse}
                entityType={formSchema.entity_type}
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
