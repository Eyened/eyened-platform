<script lang="ts">
    import Button from "$lib/components/ui/button/button.svelte";
    import Input from "$lib/components/ui/input/input.svelte";
    import {
        createFormAnnotation,
        formAnnotations,
        setFormAnnotationValue,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { ImagePoint, PointList } from "$lib/forms/pointSchema";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { etdrsGridType } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
    import { ETDRSGridItemOverlay } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import type {
        FormAnnotationGET,
        FormSchemaGET,
    } from "../../../types/openapi_types";
    import { Hide, PanelIcon, Show } from "../icons/icons";
    import { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import ETDRSGridItem from "./ETDRSGridItem.svelte";
    import ETDRSGridItemLinked from "./ETDRSGridItemLinked.svelte";
    import { SvelteMap, SvelteSet } from "svelte/reactivity";

    type LandmarkField = "fovea" | "disc_edge";

    const LANDMARK_SLOTS = ["fovea", "disc_edge"] as const;

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
    let settings = $state({ radiusFraction: 0.85 });

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

    let selectedId = $state<number | undefined>(undefined);
    let activeTool = $state<PointTool | undefined>(undefined);
    let removeTool: (() => void) | undefined;

    function isImagePoint(value: unknown): value is ImagePoint {
        return (
            typeof value === "object" &&
            value !== null &&
            typeof (value as ImagePoint).x === "number" &&
            typeof (value as ImagePoint).y === "number"
        );
    }

    function pointsFromFormData(
        data: Record<string, unknown> | undefined,
    ): PointList {
        const d = data ?? {};
        return LANDMARK_SLOTS.map((slot) => {
            const v = d[slot];
            return isImagePoint(v) ? v : null;
        });
    }

    function writeFormData(
        annotationId: number,
        points: PointList,
        persist: boolean,
    ) {
        const existing =
            formAnnotations.get(annotationId) ??
            filtered.find((f) => f.id === annotationId);
        if (!existing) return;
        const data = { ...(existing.form_data as Record<string, unknown>) };
        for (let i = 0; i < LANDMARK_SLOTS.length; i++) {
            const slot = LANDMARK_SLOTS[i]!;
            const pt = points[i] ?? null;
            if (pt == null) delete data[slot];
            else data[slot] = pt;
        }
        formAnnotations.set(annotationId, { ...existing, form_data: data });
        if (persist) setFormAnnotationValue(annotationId, data);
    }

    const placementField = $derived<LandmarkField>(
        activeTool?.placementIndex === 1 ? "disc_edge" : "fovea",
    );

    /** Landmarks live in the annotation image's pixel space — edit only there. */
    function belongsToThisImage(formAnnotation: FormAnnotationGET): boolean {
        return formAnnotation.image_id == instance.id;
    }

    function deactivateTool() {
        removeTool?.();
        removeTool = undefined;
        activeTool = undefined;
    }

    function close() {
        if (selectedId === undefined) return;
        deactivateTool();
        selectedId = undefined;
    }

    function open(
        formAnnotation: FormAnnotationGET,
        field: LandmarkField = "fovea",
    ) {
        if (!filtered.some((f) => f.id === formAnnotation.id)) return;

        const editingTool =
            selectedId === formAnnotation.id ? activeTool : undefined;
        ensureOverlay(formAnnotation);
        selectedId = formAnnotation.id;

        // PointTool must not run on linked images; landmarks use owner pixel space.
        if (
            !belongsToThisImage(formAnnotation) ||
            !globalContext.canEdit(formAnnotation)
        ) {
            deactivateTool();
            return;
        }

        // Already editing this annotation — just switch slot.
        if (editingTool) {
            editingTool.placementIndex = field === "disc_edge" ? 1 : 0;
            return;
        }

        deactivateTool();

        const annotationId = formAnnotation.id;
        const tool = new PointTool({
            canEdit: true,
            pointStyle: "cross",
            radius: 16,
            color: "rgba(0, 255, 0, 1)",
            cardinality: "list",
            sparse: true,
            slotLabels: ["Fovea", "Disc edge"],
            slotKeys: [
                { index: 0, key: "f" },
                { index: 1, key: "d" },
            ],
            onChange: (points) => writeFormData(annotationId, points, false),
            onPersist: (points) => writeFormData(annotationId, points, true),
        });
        tool.points = pointsFromFormData(
            formAnnotations.get(annotationId)?.form_data as
                | Record<string, unknown>
                | undefined,
        );
        tool.placementIndex = field === "disc_edge" ? 1 : 0;

        const dispose = viewerContext.addOverlay(tool);
        removeTool = () => {
            tool.destroy();
            dispose();
        };
        activeTool = tool;
    }

    function selectItem(formAnnotation: FormAnnotationGET) {
        if (selectedId === formAnnotation.id) {
            close();
            return;
        }
        open(formAnnotation, "fovea");
    }

    function armLandmark(
        formAnnotation: FormAnnotationGET,
        field: LandmarkField,
    ) {
        open(formAnnotation, field);
    }

    function ensureOverlay(formAnnotation: FormAnnotationGET) {
        const id = formAnnotation.id;
        if (overlayIds.has(id)) return;
        overlayIds.add(id);
        overlays.set(
            id,
            viewerContext.addOverlay(
                new ETDRSGridItemOverlay(
                    { kind: "annotation", id },
                    registration,
                    settings,
                ),
            ),
        );
    }

    function toggleOverlay(
        formAnnotation: FormAnnotationGET,
        active?: boolean,
    ) {
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

    function onRemove(formAnnotation: FormAnnotationGET) {
        toggleOverlay(formAnnotation, false);
        if (selectedId === formAnnotation.id) close();
    }

    function deactivateAll() {
        removeAutoOverlay?.();
        removeAutoOverlay = undefined;
        for (const remove of overlays.values()) remove();
        overlays.clear();
        overlayIds.clear();
        close();
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
        open(newAnnotation, "fovea");
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
            removeAutoOverlay = viewerContext.addOverlay(
                new ETDRSGridItemOverlay(
                    { kind: "snapshot", data: autoItem },
                    registration,
                    settings,
                ),
            );
        }
    }
    let showHide = $derived(removeAutoOverlay ? Show : Hide);

    $effect(() => {
        if (selectedId === undefined) return;
        if (!filtered.some((f) => f.id === selectedId)) close();
    });

    // Drop grid overlays whose FormAnnotation was deleted elsewhere.
    $effect(() => {
        const alive = new Set(filtered.map((f) => f.id));
        for (const id of [...overlayIds]) {
            if (alive.has(id)) continue;
            overlays.get(id)?.();
            overlays.delete(id);
            overlayIds.delete(id);
        }
    });
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
            {#if belongsToThisImage(formAnnotation)}
                <ETDRSGridItem
                    {formAnnotation}
                    overlayActive={overlayIds.has(formAnnotation.id)}
                    selected={selectedId === formAnnotation.id}
                    armedField={selectedId === formAnnotation.id && activeTool
                        ? placementField
                        : undefined}
                    onToggleOverlay={toggleOverlay}
                    onSelect={selectItem}
                    {onRemove}
                    onArmLandmark={armLandmark}
                />
            {:else}
                <ETDRSGridItemLinked
                    {formAnnotation}
                    overlayActive={overlayIds.has(formAnnotation.id)}
                    onToggleOverlay={toggleOverlay}
                />
            {/if}
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
