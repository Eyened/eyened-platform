<script lang="ts">
    import Button from "$lib/components/ui/button/button.svelte";
    import Input from "$lib/components/ui/input/input.svelte";
    import {
        createFormAnnotation,
        formAnnotations,
        setFormAnnotationValue,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { createMultiFieldAdapter } from "$lib/forms/pointAdapters";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { etdrsGridType } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
    import { ETDRSGridItemOverlay } from "$lib/viewer/overlays/ETDRSGridItemOverlay.svelte";
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

    // Overlay visibility (eye) is independent of selection.
    let overlayIds = new SvelteSet<number>();
    let overlays = new SvelteMap<number, () => void>();

    // Single selection model: which item is open, and which landmark receives empty clicks.
    let selectedId = $state<number | undefined>(undefined);

    /** Which landmark receives empty clicks, derived from the active point session so it
     * always reflects reality (falls back to fovea when this item isn't the armed one). */
    const placementField = $derived<LandmarkField>(
        pointArming.session?.key === `etdrs:${selectedId}` &&
            pointArming.activeSlot === 1
            ? "disc_edge"
            : "fovea",
    );

    // If another session takes over arming (a different ETDRS item, or another
    // panel entirely) while this item was the editable/armed selection, the
    // selection here goes stale: clear it so highlighting doesn't lie. Items
    // that were never armed (not editable) are left selected — they only show
    // as "open", not "armed", and don't depend on the point session.
    $effect(() => {
        if (selectedId === undefined) return;
        const formAnnotation = filtered.find((f) => f.id === selectedId);
        if (!formAnnotation || !globalContext.canEdit(formAnnotation)) return;
        if (pointArming.session?.key !== `etdrs:${selectedId}`) {
            selectedId = undefined;
        }
    });

    function close() {
        if (selectedId === undefined) return;
        const id = selectedId;
        pointArming.disarm(`etdrs:${id}`);
        selectedId = undefined;
    }

    /** Open item (show grid + arm tools). Re-open same id toggles closed. */
    function open(
        formAnnotation: FormAnnotationGET,
        field: LandmarkField = "fovea",
    ) {
        if (!filtered.some((f) => f.id === formAnnotation.id)) return;

        if (selectedId === formAnnotation.id) {
            // Same item: switching landmark only, or toggle close on root re-click
            // (root always passes default fovea — handled by selectItem).
            pointArming.setActiveSlot(field === "disc_edge" ? 1 : 0);
            return;
        }

        ensureOverlay(formAnnotation);
        selectedId = formAnnotation.id;

        if (!globalContext.canEdit(formAnnotation)) {
            pointArming.disarm();
            return;
        }

        const annotationId = formAnnotation.id;
        pointArming.arm({
            key: `etdrs:${annotationId}`,
            canEdit: true,
            pointStyle: "cross",
            radius: 16,
            color: "rgba(0, 255, 0, 1)",
            host: viewerContext,
            useActiveSlotPlacement: true,
            slotKeys: [
                { index: 0, key: "f", label: "fovea" },
                { index: 1, key: "d", label: "disc" },
            ],
            adapter: createMultiFieldAdapter({
                slots: LANDMARK_SLOTS,
                slotLabels: ["fovea", "disc"],
                getPublicId: () => instance.id,
                getFormData: () =>
                    (formAnnotations.get(annotationId)?.form_data as Record<
                        string,
                        unknown
                    >) ?? {},
                setFormData: (next) => {
                    const existing =
                        formAnnotations.get(annotationId) ??
                        filtered.find((f) => f.id === annotationId);
                    if (!existing) return;
                    formAnnotations.set(annotationId, {
                        ...existing,
                        form_data: next,
                    });
                    setFormAnnotationValue(annotationId, next);
                },
            }),
        });
        pointArming.setActiveSlot(field === "disc_edge" ? 1 : 0);
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
        if (selectedId === formAnnotation.id) {
            pointArming.setActiveSlot(field === "disc_edge" ? 1 : 0);
            return;
        }
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
                selected={selectedId === formAnnotation.id}
                armedField={selectedId === formAnnotation.id
                    ? placementField
                    : undefined}
                onToggleOverlay={toggleOverlay}
                onSelect={selectItem}
                onRemove={onRemove}
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
