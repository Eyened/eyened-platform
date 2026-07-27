<script lang="ts">
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";
    import { Hide, PanelIcon, Show } from "../icons/icons";

    const taskContext = getContext<TaskContext>("taskContext");
    const subTask = taskContext?.subTask;

    interface Props {
        formAnnotation: FormAnnotationGET;
        overlayActive: boolean;
        onToggleOverlay: (
            formAnnotation: FormAnnotationGET,
            active?: boolean,
        ) => void;
    }
    let { formAnnotation, overlayActive, onToggleOverlay }: Props = $props();

    const sameSubTask = formAnnotation.sub_task_id === subTask?.id;
    const showHide = $derived(overlayActive ? Show : Hide);

    function toggleOverlay(e: MouseEvent) {
        e.stopPropagation();
        onToggleOverlay(formAnnotation);
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
        </nav>
        <div class="annotation-id">
            <span class="creator-name">{formAnnotation.creator.name}</span>
            <span class="image-id-value">[{formAnnotation.image_id}]</span>
            <code class="annotation-id-value">[{formAnnotation.id}]</code>
        </div>
    </header>
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

    div.annotation-id {
        display: flex;
        gap: 0.3em;
        font-size: x-small;
        align-items: center;
    }

    span.creator-name,
    span.image-id-value {
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
</style>
