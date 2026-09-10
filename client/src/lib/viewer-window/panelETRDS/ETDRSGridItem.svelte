<script lang="ts">
    import { deleteFormAnnotation } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { Position2D } from "$lib/types";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";
    import { Hide, PanelIcon, Show, Trash } from "../icons/icons";

    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const subTask = taskContext?.subTask;

    type LandmarkField = "fovea" | "disc_edge";

    interface Props {
        formAnnotation: FormAnnotationGET;
        overlayActive: boolean;
        selected: boolean;
        armedField?: LandmarkField;
        onToggleOverlay: (
            formAnnotation: FormAnnotationGET,
            active?: boolean,
        ) => void;
        onSelect: (formAnnotation: FormAnnotationGET) => void;
        onRemove: (formAnnotation: FormAnnotationGET) => void;
        onArmLandmark: (
            formAnnotation: FormAnnotationGET,
            field: LandmarkField,
        ) => void;
    }
    let {
        formAnnotation,
        overlayActive,
        selected,
        armedField,
        onToggleOverlay,
        onSelect,
        onRemove,
        onArmLandmark,
    }: Props = $props();

    const sameSubTask = formAnnotation.sub_task_id === subTask?.id;

    const fovea: Position2D | undefined = $derived(
        (formAnnotation.form_data as any)?.fovea as Position2D | undefined,
    );
    const disc_edge: Position2D | undefined = $derived(
        (formAnnotation.form_data as any)?.disc_edge as Position2D | undefined,
    );

    const canEditForm = globalContext.canEdit(formAnnotation);
    const showHide = $derived(overlayActive ? Show : Hide);

    function formatCoords(p: Position2D | undefined) {
        if (!p) return "—";
        return `[${Math.round(p.x)}, ${Math.round(p.y)}]`;
    }

    function selectRoot(e: MouseEvent) {
        e.stopPropagation();
        onSelect(formAnnotation);
    }

    function toggleOverlay(e: MouseEvent) {
        e.stopPropagation();
        onToggleOverlay(formAnnotation);
    }

    function remove(e: MouseEvent) {
        e.stopPropagation();
        onRemove(formAnnotation);
        deleteFormAnnotation(formAnnotation.id);
    }

    function armLandmark(e: MouseEvent, field: LandmarkField) {
        e.stopPropagation();
        if (!canEditForm) return;
        onArmLandmark(formAnnotation, field);
    }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<article
    class="info"
    class:same-sub-task={sameSubTask}
    class:selected
    onclick={selectRoot}
>
    <header class="top">
        <nav class="icons" aria-label="Annotation actions">
            <PanelIcon
                active={overlayActive}
                onclick={toggleOverlay}
                tooltip="show/hide"
                Icon={showHide}
            />

            {#if canEditForm}
                <span class="spacer" aria-hidden="true"></span>
                <PanelIcon onclick={remove} tooltip="delete" Icon={Trash} />
            {/if}
        </nav>
        <div class="annotation-id">
            <span class="creator-name">{formAnnotation.creator.name}</span>
            <code class="annotation-id-value">[{formAnnotation.id}]</code>
        </div>
    </header>
    <div class="landmarks">
        <button
            type="button"
            class="landmark"
            class:armed={selected && armedField === "fovea"}
            disabled={!canEditForm}
            title={!canEditForm ? "Editing not allowed" : undefined}
            onclick={(e) => armLandmark(e, "fovea")}
        >
            <span class="name">Fovea (f)</span>
            <code class="coords">{formatCoords(fovea)}</code>
        </button>
        <button
            type="button"
            class="landmark"
            class:armed={selected && armedField === "disc_edge"}
            disabled={!canEditForm}
            title={!canEditForm ? "Editing not allowed" : undefined}
            onclick={(e) => armLandmark(e, "disc_edge")}
        >
            <span class="name">Disc (d)</span>
            <code class="coords">{formatCoords(disc_edge)}</code>
        </button>
    </div>
    <dl class="details">
        <div>
            <dt>ImageID:</dt>
            <dd>
                <code class="value">{formAnnotation.image_id}</code>
            </dd>
        </div>
    </dl>
</article>

<style>
    article.info {
        display: flex;
        background-color: rgba(255, 255, 255, 0.1);
        flex-direction: column;
        border: 1px solid black;
        border-radius: 2px;
        padding: 0.2em;
        cursor: pointer;
    }

    article.info.same-sub-task {
        background-color: rgba(100, 255, 100, 0.2);
    }

    article.info:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }

    article.info:hover.same-sub-task {
        background-color: rgba(100, 255, 100, 0.4);
    }

    article.info.selected {
        border-color: rgb(57, 158, 165);
        box-shadow: inset 0 0 0 1px rgb(57, 158, 165);
        background-color: rgba(57, 158, 165, 0.22);
    }

    article.info.selected.same-sub-task {
        background-color: rgba(57, 158, 165, 0.28);
    }

    header.top {
        display: flex;
        align-items: center;
        gap: 0.5em;
    }

    nav.icons {
        display: flex;
        flex: 1;
        align-items: center;
        gap: 0.2em;
        user-select: none;
    }

    span.spacer {
        flex: 1;
    }

    div.landmarks {
        display: flex;
        gap: 0.25em;
        padding: 0.15em 0;
        flex-wrap: wrap;
    }

    button.landmark {
        display: inline-flex;
        align-items: center;
        gap: 0.35em;
        padding: 0.1em 0.35em;
        font-size: 0.7rem;
        line-height: 1.2;
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 2px;
        background: rgba(0, 0, 0, 0.25);
        color: inherit;
        cursor: pointer;
        opacity: 1;
    }

    button.landmark:hover:not(:disabled) {
        background: rgba(255, 255, 255, 0.15);
    }

    button.landmark:disabled {
        cursor: not-allowed;
        opacity: 0.45;
    }

    button.landmark.armed {
        background: rgb(57, 158, 165);
        border-color: rgb(57, 158, 165);
        color: white;
    }

    button.landmark .name {
        font-weight: 600;
        white-space: nowrap;
    }

    button.landmark .coords {
        font-family: monospace;
        font-size: 0.95em;
        opacity: 0.9;
    }

    div.annotation-id {
        display: flex;
        gap: 0.3em;
        font-size: x-small;
        align-items: center;
    }

    span.creator-name {
        user-select: text;
    }

    code.annotation-id-value {
        user-select: text;
        font-family: inherit;
        font-size: inherit;
        background: transparent;
        padding: 0;
        border: none;
    }

    dl.details {
        display: flex;
        flex-direction: column;
        list-style-type: none;
        padding: 0;
        margin: 0;
        font-size: xx-small;
        gap: 0.2em;
    }

    dl.details > div {
        display: flex;
        align-items: center;
        gap: 0.5em;
    }

    dt {
        font-weight: normal;
        user-select: text;
        min-width: fit-content;
    }

    dd {
        margin: 0;
        display: flex;
        flex: 1;
    }

    code.value {
        user-select: text;
        font-family: inherit;
        font-size: inherit;
        background: transparent;
        padding: 0;
        border: none;
    }
</style>
