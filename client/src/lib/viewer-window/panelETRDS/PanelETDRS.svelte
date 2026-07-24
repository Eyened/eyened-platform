<script lang="ts">
    import Button from "$lib/components/ui/button/button.svelte";
    import Input from "$lib/components/ui/input/input.svelte";
    import {
        createFormAnnotation,
        formAnnotations,
        setFormAnnotationValue,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import {
        analyzePointSchema,
        type ImagePoint,
    } from "$lib/forms/pointSchema";
    import type { JSONSchema } from "$lib/forms/schemaType";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { etdrsGridType } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
    import { ETDRSGridItemOverlay } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { ViewerEvent } from "$lib/viewer/viewer-utils";
    import { getContext } from "svelte";
    import type {
        FormAnnotationGET,
        FormSchemaGET,
    } from "../../../types/openapi_types";
    import { Hide, PanelIcon, Show } from "../icons/icons";
    import { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import ETDRSGridItem from "./ETDRSGridItem.svelte";
    import { SvelteMap, SvelteSet } from "svelte/reactivity";

    type LandmarkField = "fovea" | "disc_edge";

    interface Props {
        active: boolean;
        etdrsSchema: FormSchemaGET;
    }
    let { etdrsSchema }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const registration = viewerWindowContext.registration;

    const image = viewerContext.image;
    const instance = image.instance;
    const image_id = image.image_id;
    let settings = $state({
        radiusFraction: 0.85,
    });
    const filtered = $derived(
        formAnnotations.filter((formAnnotation) => {
            if (formAnnotation.form_schema_id !== etdrsSchema.id) return false;

            if (formAnnotation.image_id == instance.id) return true;

            const linkedIDs = registration.getLinkedImgIds(image_id);
            if (linkedIDs.has(`${formAnnotation.image_id}`)) return true;
            if (linkedIDs.has(`${formAnnotation.image_id}_proj`)) return true;
            return false;
        }),
    );

    let overlayIds = new SvelteSet<number>();
    let overlays = new SvelteMap<number, () => void>();

    let armedAnnotationId = $state<number | undefined>(undefined);
    let armedField = $state<LandmarkField | undefined>(undefined);

    function landmarkAnalysis(field: LandmarkField) {
        const props = (etdrsSchema.schema as JSONSchema).properties?.[field];
        const withWidget: JSONSchema = {
            ...(props ?? {}),
            "x-eyened-widget": "point",
            type: "object",
            properties: {
                x: { type: "number" },
                y: { type: "number" },
            },
            required: ["x", "y"],
        };
        return analyzePointSchema(withWidget, "ImageInstance")!;
    }

    function placeLandmarkAtCursor(
        formAnnotation: FormAnnotationGET,
        field: LandmarkField,
        e: ViewerEvent<KeyboardEvent>,
    ) {
        if (!globalContext.canEdit(formAnnotation)) return;
        const position = e.viewerContext.viewerToImageCoordinates(e.cursor);
        const point: ImagePoint = { x: position.x, y: position.y };
        const form_data = {
            ...(formAnnotation.form_data || {}),
            [field]: point,
        };
        formAnnotation.form_data = form_data;
        setFormAnnotationValue(formAnnotation.id, form_data);
        armLandmark(formAnnotation, field);
    }

    function armLandmark(
        formAnnotation: FormAnnotationGET,
        field: LandmarkField,
    ) {
        if (!filtered.some((f) => f.id === formAnnotation.id)) return;
        if (!globalContext.canEdit(formAnnotation)) return;

        const key = `etdrs:${formAnnotation.id}:${field}`;
        const analysis = landmarkAnalysis(field);

        pointArming.arm(key, () => {
            armedAnnotationId = formAnnotation.id;
            armedField = field;
            const dispose = viewerContext.addOverlay(
                new PointTool({
                    canEdit: true,
                    analysis,
                    label: field,
                    getPublicId: () => instance.id,
                    getFieldValue: () =>
                        (formAnnotation.form_data as any)?.[field],
                    setFieldValue: (next) => {
                        const form_data = {
                            ...(formAnnotation.form_data || {}),
                            [field]: next,
                        };
                        formAnnotation.form_data = form_data;
                        setFormAnnotationValue(formAnnotation.id, form_data);
                    },
                    onKey: (e) => {
                        const k = e.event.key.toLowerCase();
                        if (k === "f") {
                            placeLandmarkAtCursor(formAnnotation, "fovea", e);
                        } else if (k === "d") {
                            placeLandmarkAtCursor(
                                formAnnotation,
                                "disc_edge",
                                e,
                            );
                        }
                    },
                }),
            );
            return () => {
                dispose();
                if (armedAnnotationId === formAnnotation.id) {
                    armedAnnotationId = undefined;
                    armedField = undefined;
                }
            };
        });
    }

    function deactivateAll() {
        removeAutoOverlay?.();
        removeAutoOverlay = undefined;
        for (const remove of overlays.values()) remove();
        overlays.clear();
        overlayIds.clear();
        pointArming.disarm();
        armedAnnotationId = undefined;
        armedField = undefined;
    }

    function toggleOverlay(
        formAnnotation: FormAnnotationGET,
        active?: boolean,
    ) {
        if (!filtered.some((f) => f.id === formAnnotation.id)) return;
        const id = formAnnotation.id;
        const isActive = overlayIds.has(id);
        const shouldBeActive = active !== undefined ? active : !isActive;
        if (shouldBeActive === isActive) return;

        if (shouldBeActive) {
            overlayIds.add(id);
            overlays.set(
                id,
                viewerContext.addOverlay(
                    new ETDRSGridItemOverlay(
                        formAnnotation as any,
                        registration,
                        settings,
                    ),
                ),
            );
        } else {
            overlays.get(id)?.();
            overlays.delete(id);
            overlayIds.delete(id);
        }
    }

    function toggleTool(formAnnotation: FormAnnotationGET, active?: boolean) {
        if (!filtered.some((f) => f.id === formAnnotation.id)) return;
        if (!globalContext.canEdit(formAnnotation)) return;

        const isActive = armedAnnotationId === formAnnotation.id;
        const shouldBeActive = active !== undefined ? active : !isActive;

        if (!shouldBeActive) {
            if (isActive) {
                pointArming.disarm();
                armedAnnotationId = undefined;
                armedField = undefined;
            }
            return;
        }

        if (isActive) return;
        armLandmark(formAnnotation, "fovea");
    }

    async function create() {
        deactivateAll();
        const newAnnotation = await createFormAnnotation({
            form_schema_id: etdrsSchema.id,
            patient_id: instance.patient.id,
            study_id: instance.study?.id ?? undefined,
            image_id: instance.id,
            laterality: instance.laterality ?? undefined,
            sub_task_id: taskContext?.subTask?.id,
            form_data: {},
        });
        toggleOverlay(newAnnotation, true);
        armLandmark(newAnnotation, "fovea");
    }

    const autoItem: etdrsGridType | undefined = $derived.by(() => {
        if (!instance.cf_keypoints) return undefined;
        const [fx, fy] = instance.cf_keypoints.fovea_xy as [number, number];
        const [odx, ody] = instance.cf_keypoints.disc_edge_xy as [
            number,
            number,
        ];
        return {
            image_id: String(image_id),
            form_data: {
                fovea: { x: fx, y: fy },
                disc_edge: { x: odx, y: ody },
            },
        };
    });

    let removeAutoOverlay: (() => void) | undefined = $state(undefined);
    function toggleVisisble() {
        if (!autoItem) return;
        if (removeAutoOverlay) {
            removeAutoOverlay();
            removeAutoOverlay = undefined;
        } else {
            const itemOverlay = new ETDRSGridItemOverlay(
                autoItem,
                registration,
                settings,
            );
            removeAutoOverlay = viewerContext.addOverlay(itemOverlay);
        }
    }
    let showHide = $derived(removeAutoOverlay ? Show : Hide);
</script>

<div class="main">
    <div class="etdrs-fraction">
        <label for="etdrsRadiusFraction">ETDRS radius fraction:</label>
        <Input
            type="number"
            id="etdrsRadiusFraction"
            bind:value={settings.radiusFraction}
            step="0.01"
            min="0.01"
            max="1"
        />
    </div>
    <div class="available">
        {#if autoItem}
            <div class="automatic">
                <PanelIcon
                    active={removeAutoOverlay != undefined}
                    onclick={toggleVisisble}
                    tooltip="show/hide"
                    Icon={showHide}
                />

                Automatic
            </div>
        {/if}

        {#each filtered as formAnnotation (formAnnotation.id)}
            <ETDRSGridItem
                {formAnnotation}
                {settings}
                overlayActive={overlayIds.has(formAnnotation.id)}
                toolActive={armedAnnotationId === formAnnotation.id}
                armedField={armedAnnotationId === formAnnotation.id
                    ? armedField
                    : undefined}
                onToggleOverlay={toggleOverlay}
                onToggleTool={toggleTool}
                onArmLandmark={armLandmark}
            />
        {/each}
    </div>
    <div class="new">
        <Button onclick={create}>Create new</Button>
    </div>
</div>

<style>
    div.main {
        padding: 0.5em;
        flex: 1;
    }
    div.etdrs-fraction {
        display: flex;
        align-items: center;
        gap: 0.5em;
    }

    div.automatic {
        display: flex;
        background-color: rgba(255, 255, 255, 0.1);
        align-items: center;
        border: 1px solid black;
        border-radius: 2px;
        padding: 0.2em;
    }
    div.automatic:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }
</style>
