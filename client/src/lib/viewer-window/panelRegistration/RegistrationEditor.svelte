<script lang="ts">
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
    import { formAnnotations, formSchemas } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { JSONSchema } from "$lib/forms/schemaType";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext, onMount } from "svelte";
    import { CLIENT_DEFAULTS, mergeClientConfig } from "../taskConfigLayout";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import RegistrationBlend from "./RegistrationBlend.svelte";
    import RegistrationThumbnail from "./RegistrationThumbnail.svelte";

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext | undefined>("taskContext");

    const session = $derived(viewerWindowContext.registrationEditor);

    function resolveImages(
        imageIds: readonly string[],
    ): AbstractImage[] | null {
        const images: AbstractImage[] = [];
        for (const id of imageIds) {
            let match: AbstractImage | undefined;
            for (const image of viewerWindowContext.topViewers.keys()) {
                if (image.image_id === id) {
                    match = image;
                    break;
                }
            }
            if (!match) return null;
            images.push(match);
        }
        return images;
    }

    const images = $derived(session ? resolveImages(session.imageIds) : null);

    // A missing id would leave background viewers paused, so close instead.
    $effect.pre(() => {
        const current = viewerWindowContext.registrationEditor;
        if (!current) return;
        if (!resolveImages(current.imageIds)) {
            viewerWindowContext.closeRegistrationEditor();
        }
    });

    const pointSchema = $derived.by(() => {
        const formSchema = formSchemas.find(
            (schema) =>
                schema.name ===
                BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION,
        );
        return (formSchema?.schema ?? {}) as JSONSchema;
    });

    const pointMarker = $derived(
        mergeClientConfig(
            CLIENT_DEFAULTS,
            taskContext?.task.task_definition.config,
        ).point_marker,
    );

    const canEdit = $derived.by(() => {
        if (!session) return false;
        const annotation = formAnnotations.get(session.annotationId);
        if (!annotation) return false;
        return globalContext.canEdit(annotation);
    });

    let root: HTMLDivElement | undefined = $state();

    onMount(() => {
        root?.focus();
    });
</script>

{#if session && images}
    <div
        class="editor"
        bind:this={root}
        role="dialog"
        aria-modal="true"
        aria-label="Registration editor"
        tabindex="-1"
    >
        <button
            type="button"
            class="close"
            onclick={() => viewerWindowContext.closeRegistrationEditor()}
        >
            Close
        </button>
        <div class="thumbs">
            {#each images as image (image.image_id)}
                <RegistrationThumbnail
                    {image}
                    annotationId={session.annotationId}
                    schema={pointSchema}
                    {canEdit}
                    {pointMarker}
                />
            {/each}
        </div>
        <RegistrationBlend {images} />
    </div>
{/if}

<style>
    .editor {
        position: fixed;
        inset: 0;
        z-index: 20;
        /* The window canvas is cleared black and sits under this layer.
           An opaque background here would cover the blended images. */
        background: transparent;
        display: flex;
        flex-direction: column;
        outline: none;
    }

    .close {
        position: absolute;
        top: 0.4em;
        right: 0.4em;
        z-index: 2;
    }

    .thumbs {
        height: 20%;
        min-height: 0;
        display: flex;
    }
</style>
