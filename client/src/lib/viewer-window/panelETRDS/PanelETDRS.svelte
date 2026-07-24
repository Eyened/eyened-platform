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
    } from "$lib/forms/pointSchema";
    import type { JSONSchema } from "$lib/forms/schemaType";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { etdrsGridType } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
    import { ETDRSGridItemOverlay } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
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

    const LANDMARKS: LandmarkField[] = ["fovea", "disc_edge"];
    const LANDMARK_LABEL: Record<LandmarkField, string> = {
        fovea: "fovea",
        disc_edge: "disc",
    };
    const LANDMARK_KEY: Record<LandmarkField, string> = {
        fovea: "f",
        disc_edge: "d",
    };

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

    let selectedAnnotationId = $state<number | undefined>(undefined);
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

    function writeLandmark(
        annotationId: number,
        field: LandmarkField,
        next: unknown,
    ) {
        const existing =
            formAnnotations.get(annotationId) ??
            filtered.find((f) => f.id === annotationId);
        if (!existing) return;
        const form_data = {
            ...(existing.form_data || {}),
            [field]: next,
        };
        formAnnotations.set(annotationId, { ...existing, form_data });
        setFormAnnotationValue(annotationId, form_data);
    }

    /** Mount both landmark PointTools; armedField selects empty-click placement. */
    function startEdit(
        formAnnotation: FormAnnotationGET,
        initialField: LandmarkField = "fovea",
    ) {
        if (!filtered.some((f) => f.id === formAnnotation.id)) return;
        if (!globalContext.canEdit(formAnnotation)) return;

        const annotationId = formAnnotation.id;
        const sessionKey = `etdrs:${annotationId}`;

        if (pointArming.isArmed(sessionKey)) {
            selectedAnnotationId = annotationId;
            armedAnnotationId = annotationId;
            armedField = initialField;
            return;
        }

        pointArming.arm(sessionKey, () => {
            selectedAnnotationId = annotationId;
            armedAnnotationId = annotationId;
            armedField = initialField;

            const disposers: Array<() => void> = [];

            for (const field of LANDMARKS) {
                const tool = new PointTool({
                    canEdit: true,
                    analysis: landmarkAnalysis(field),
                    label: LANDMARK_LABEL[field],
                    pointStyle: "circle",
                    radius: 16,
                    color: "rgba(0, 255, 0, 1)",
                    getPublicId: () => instance.id,
                    getFieldValue: () =>
                        (formAnnotations.get(annotationId)?.form_data as any)?.[
                            field
                        ],
                    setFieldValue: (next) =>
                        writeLandmark(annotationId, field, next),
                    isPlacementTarget: () => armedField === field,
                    onBecomePlacementTarget: () => {
                        armedField = field;
                    },
                    placeKey: LANDMARK_KEY[field],
                });
                const remove = viewerContext.addOverlay(tool);
                disposers.push(() => {
                    tool.destroy();
                    remove();
                });
            }

            return () => {
                for (const d of disposers) d();
                if (armedAnnotationId === annotationId) {
                    armedAnnotationId = undefined;
                    armedField = undefined;
                }
                if (selectedAnnotationId === annotationId) {
                    selectedAnnotationId = undefined;
                }
            };
        });
    }

    function setPlacementTarget(
        formAnnotation: FormAnnotationGET,
        field: LandmarkField,
    ) {
        ensureOverlay(formAnnotation);
        selectedAnnotationId = formAnnotation.id;
        if (armedAnnotationId === formAnnotation.id) {
            armedField = field;
            return;
        }
        startEdit(formAnnotation, field);
    }

    function stopEdit() {
        pointArming.disarm();
        armedAnnotationId = undefined;
        armedField = undefined;
    }

    function stopEditFor(formAnnotation: FormAnnotationGET) {
        if (armedAnnotationId === formAnnotation.id) stopEdit();
        if (selectedAnnotationId === formAnnotation.id) {
            selectedAnnotationId = undefined;
        }
    }

    /** Open/select item: show grid overlay and arm point tools (f/d). */
    function selectItem(formAnnotation: FormAnnotationGET) {
        if (!filtered.some((f) => f.id === formAnnotation.id)) return;

        if (selectedAnnotationId === formAnnotation.id) {
            // Clicking the selected item again closes it; overlay stays unless
            // the user hides it via the eye icon.
            stopEdit();
            selectedAnnotationId = undefined;
            return;
        }

        ensureOverlay(formAnnotation);
        selectedAnnotationId = formAnnotation.id;
        if (globalContext.canEdit(formAnnotation)) {
            startEdit(formAnnotation, "fovea");
        } else {
            stopEdit();
        }
    }

    function deactivateAll() {
        removeAutoOverlay?.();
        removeAutoOverlay = undefined;
        for (const remove of overlays.values()) remove();
        overlays.clear();
        overlayIds.clear();
        stopEdit();
        selectedAnnotationId = undefined;
    }

    function ensureOverlay(formAnnotation: FormAnnotationGET) {
        if (!filtered.some((f) => f.id === formAnnotation.id)) return;
        const id = formAnnotation.id;
        if (overlayIds.has(id)) return;

        overlayIds.add(id);
        overlays.set(
            id,
            viewerContext.addOverlay(
                new ETDRSGridItemOverlay(
                    { kind: "annotation", id: formAnnotation.id },
                    registration,
                    settings,
                ),
            ),
        );
    }

    /** Eye icon only — show/hide grid overlay; does not open/close selection. */
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
            ensureOverlay(formAnnotation);
        } else {
            overlays.get(id)?.();
            overlays.delete(id);
            overlayIds.delete(id);
        }
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
        selectItem(newAnnotation);
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
                { kind: "snapshot", data: autoItem },
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
                selected={selectedAnnotationId === formAnnotation.id}
                armedField={armedAnnotationId === formAnnotation.id
                    ? armedField
                    : undefined}
                onToggleOverlay={toggleOverlay}
                onSelect={selectItem}
                onStopEdit={stopEditFor}
                onArmLandmark={setPlacementTarget}
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
