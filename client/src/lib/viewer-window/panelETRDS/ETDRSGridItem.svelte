<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import { deleteFormAnnotation } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { Position2D } from "$lib/types";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";
    import { Edit, Hide, PanelIcon, Show, Trash } from "../icons/icons";

    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const subTask = taskContext?.subTask;

    type LandmarkField = "fovea" | "disc_edge";

    interface Props {
        formAnnotation: FormAnnotationGET;
        settings: { radiusFraction: number };
        overlayActive: boolean;
        toolActive: boolean;
        armedField?: LandmarkField;
        onToggleOverlay: (
            formAnnotation: FormAnnotationGET,
            active?: boolean,
        ) => void;
        onToggleTool: (
            formAnnotation: FormAnnotationGET,
            active?: boolean,
        ) => void;
        onArmLandmark: (
            formAnnotation: FormAnnotationGET,
            field: LandmarkField,
        ) => void;
    }
    let {
        formAnnotation,
        overlayActive,
        toolActive,
        armedField,
        onToggleOverlay,
        onToggleTool,
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

    function toggleOverlay() {
        onToggleOverlay(formAnnotation);
    }

    function toggleTool() {
        onToggleTool(formAnnotation);
    }

    function remove() {
        onToggleOverlay(formAnnotation, false);
        onToggleTool(formAnnotation, false);
        deleteFormAnnotation(formAnnotation.id);
    }
</script>

<article class="info" class:same-sub-task={sameSubTask}>
    <header class="top">
        <nav class="icons" aria-label="Annotation actions">
            <PanelIcon
                active={overlayActive}
                onclick={toggleOverlay}
                tooltip="show/hide"
                Icon={showHide}
            />

            {#if canEditForm}
                <PanelIcon
                    active={toolActive}
                    onclick={toggleTool}
                    tooltip="edit"
                    Icon={Edit}
                />
            {/if}
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
    {#if toolActive && canEditForm}
        <div class="landmarks">
            <Button
                size="sm"
                variant={armedField === "fovea" ? "default" : "outline"}
                onclick={() => onArmLandmark(formAnnotation, "fovea")}
            >
                Fovea (f)
            </Button>
            <Button
                size="sm"
                variant={armedField === "disc_edge" ? "default" : "outline"}
                onclick={() => onArmLandmark(formAnnotation, "disc_edge")}
            >
                Disc (d)
            </Button>
        </div>
    {/if}
    <dl class="details">
        <div>
            <dt>ImageID:</dt>
            <dd>
                <code class="value">{formAnnotation.image_id}</code>
            </dd>
        </div>

        {#if fovea}
            <div>
                <dt>fovea:</dt>
                <dd>
                    <code class="value">
                        [{Math.round(fovea.x)}, {Math.round(fovea.y)}]
                    </code>
                </dd>
            </div>
        {/if}
        {#if disc_edge}
            <div>
                <dt>disc_edge:</dt>
                <dd>
                    <code class="value">
                        [{Math.round(disc_edge.x)}, {Math.round(disc_edge.y)}]
                    </code>
                </dd>
            </div>
        {/if}
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
        gap: 0.35em;
        padding: 0.2em 0;
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
