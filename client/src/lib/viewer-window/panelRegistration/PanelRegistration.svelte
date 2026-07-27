<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import {
        createFormAnnotation,
        deleteFormAnnotation,
        formAnnotations,
        instances,
        setFormAnnotationValue,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import {
        analyzePointSchema,
        getPointsForImage,
        setPointsForImage,
    } from "$lib/forms/pointSchema";
    import type { JSONSchema } from "$lib/forms/schemaType";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import type {
        FormAnnotationGET,
        FormSchemaGET,
    } from "../../../types/openapi_types";
    import RegistrationItem from "./RegistrationItem.svelte";

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const globalContext = getContext<GlobalContext>("globalContext");

    const pointMarker = $derived(
        mergeClientConfig(
            CLIENT_DEFAULTS,
            taskContext?.task.task_definition.config,
        ).point_marker,
    );

    interface props {
        active: boolean;
        registrationSchema: FormSchemaGET;
    }
    const { active: panelActive, registrationSchema }: props = $props();

    const {
        image: { instance },
    } = viewerContext;

    const filtered = $derived(
        formAnnotations
            .filter((formAnnotation) => {
                if (formAnnotation.form_schema_id !== registrationSchema.id)
                    return false;
                if (formAnnotation.patient_id !== instance.patient.id)
                    return false;
                const formLaterality =
                    formAnnotation.laterality ??
                    (formAnnotation.image_id
                        ? instances.get(formAnnotation.image_id)?.laterality
                        : undefined);
                if (
                    formLaterality &&
                    instance.laterality &&
                    formLaterality !== instance.laterality
                ) {
                    return false;
                }
                return true;
            })
            .sort((a, b) => a.id - b.id),
    );

    const REGISTRATION_POINTS: JSONSchema = {
        type: "array",
        items: {
            oneOf: [
                {
                    type: "object",
                    properties: {
                        x: { type: "number" },
                        y: { type: "number" },
                    },
                    required: ["x", "y"],
                },
                { type: "null" },
            ],
        },
    };

    function registrationAnalysis() {
        const fromApi = (registrationSchema.schema ?? {}) as JSONSchema;
        const entityType = registrationSchema.entity_type ?? "Eye";
        const withMarkers = (schema: JSONSchema): JSONSchema => ({
            ...schema,
            type: "object",
            "x-eyened-widget": "point",
            "x-eyened-point-mode": "registration",
        });

        return (
            analyzePointSchema(withMarkers(fromApi), entityType) ??
            analyzePointSchema(
                withMarkers({ additionalProperties: REGISTRATION_POINTS }),
                entityType,
            )
        );
    }

    async function create() {
        const formAnnotation = await createFormAnnotation({
            form_schema_id: registrationSchema.id,
            patient_id: instance.patient.id,
            study_id: instance.study?.id ?? undefined,
            image_id: instance.id,
            laterality: instance.laterality ?? undefined,
            sub_task_id: taskContext?.subTask?.id,
            form_data: {},
        });
        onactivate(formAnnotation);
    }

    /** Per-viewer tool — other MainViewers can arm the same annotation independently. */
    let activeID: number | undefined = $state(undefined);
    let removeTool: (() => void) | undefined;

    function deactivate() {
        removeTool?.();
        removeTool = undefined;
        activeID = undefined;
    }

    function onactivate(formAnnotation: FormAnnotationGET) {
        const stillExists = filtered.some((f) => f.id === formAnnotation.id);
        if (!stillExists) {
            console.log("Annotation no longer exists, ignoring onactivate");
            return;
        }

        if (activeID === formAnnotation.id) {
            deactivate();
            return;
        }

        const analysis = registrationAnalysis();
        if (!analysis) {
            console.error(
                "Pointset registration schema could not be analyzed",
                registrationSchema.schema,
            );
            return;
        }

        deactivate();

        const annotationId = formAnnotation.id;
        const canEdit = globalContext.canEdit(formAnnotation);
        const publicId = () => viewerContext.image.instance.id;

        const tool = new PointTool({
            canEdit,
            label: "registration",
            pointStyle: pointMarker.style,
            radius: pointMarker.radius,
            color: pointMarker.color,
            cardinality: "list",
            registrationMode: true,
            onChange: (points) => {
                const existing =
                    formAnnotations.get(annotationId) ?? formAnnotation;
                const next = setPointsForImage(
                    existing.form_data,
                    publicId(),
                    points,
                    analysis,
                );
                formAnnotations.set(annotationId, {
                    ...existing,
                    form_data: next,
                });
            },
            onPersist: (points) => {
                const existing =
                    formAnnotations.get(annotationId) ?? formAnnotation;
                const next = setPointsForImage(
                    existing.form_data,
                    publicId(),
                    points,
                    analysis,
                );
                formAnnotations.set(annotationId, {
                    ...existing,
                    form_data: next,
                });
                setFormAnnotationValue(annotationId, next);
            },
        });

        const existing =
            formAnnotations.get(annotationId)?.form_data ??
            formAnnotation.form_data;
        tool.points = getPointsForImage(existing, publicId(), analysis);

        const dispose = viewerContext.addOverlay(tool);
        removeTool = () => {
            tool.destroy();
            dispose();
        };
        activeID = annotationId;
    }

    function onremove(formAnnotation: FormAnnotationGET) {
        if (activeID === formAnnotation.id) deactivate();
        deleteFormAnnotation(formAnnotation.id);
    }

    $effect(() => {
        if (!panelActive) deactivate();
    });

    // Unmount when the armed annotation is deleted (this viewer or another).
    $effect(() => {
        if (activeID === undefined) return;
        if (!formAnnotations.has(activeID)) deactivate();
    });
</script>

<div class="main">
    <div class="available">
        <ul>
            {#each filtered as formAnnotation (formAnnotation.id)}
                <RegistrationItem
                    {formAnnotation}
                    active={activeID === formAnnotation.id}
                    {onactivate}
                    {onremove}
                />
            {/each}
        </ul>
    </div>
    <div class="new">
        <Button variant="outline" onclick={create}>Create new</Button>
    </div>
</div>

<style>
    div.main {
        padding: 0.5em;
        min-height: 0;
        flex: 1 1 auto;
        overflow-y: auto;
        min-height: 0px;
    }
    div.new,
    div.available {
        padding: 0.2em;
        margin-bottom: 0.5em;
    }
    ul {
        list-style-type: none;
        padding-inline-start: 0em;
    }
</style>
