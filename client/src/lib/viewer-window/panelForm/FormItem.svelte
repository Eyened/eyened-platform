<script lang="ts">
    import FormItemContent from "./FormItemContent.svelte";
    import { PanelIcon, Trash } from "../icons/icons";
    import { data } from "$lib/datamodel/model";
    import type { FormAnnotation } from "$lib/datamodel/formAnnotation";
    import { openNewWindow } from "$lib/newWindow";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import { globalContext } from "$lib/main";
    import Duplicate from "../icons/Duplicate.svelte";
    import type { TaskContext } from "$lib/types";

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const taskContext = getContext<TaskContext>("taskContext");

    const { creator } = globalContext;

    interface Props {
        form: FormAnnotation;
        theme?: "light" | "dark";
    }

    let { form, theme = "dark" }: Props = $props();
    const { formAnnotations } = data;

    const dt = new Date().getTime() - (form.created?.getTime() ?? 0);
    const daysSinceCreation = dt / (1000 * 60 * 60 * 24);
    const canEditForm = globalContext.canEdit(form);

    let removing: number | undefined = $state();
    let timeout: ReturnType<typeof setTimeout> | undefined = $state();
    let progress = $state(0);
    let maxTime = 3000; // 3 seconds

    function deleteAnnotation() {
        progress = 0;
        removing = setInterval(() => {
            progress += 10;
            if (progress >= maxTime) {
                clearInterval(removing);
                removing = undefined;
                formAnnotations.delete(form);
            }
        }, 10);
    }
    function duplicate() {
        const item: any = { ...form };
        item.creator = creator;
        if (taskContext) {
            item.subTask = taskContext.subTask;
        } else {
            item.subTask = undefined;
        }
        item.reference = form;
        formAnnotations.create(item);
    }

    let window: Window | null = null;
    function openInNewWindow(form: FormAnnotation) {
        if (window) {
            window.close();
        }
        const props = { form, viewerContext, canEdit: canEditForm } as const;

        window = openNewWindow(
            FormItemContent,
            props,
            `${form.formSchema.name} ${form.id}`,
        );
    }

    function formatDateTime(dateString: string) {
        const date = new Date(dateString);
        return date.toLocaleString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    const date = form.created?.toISOString() ?? "";
</script>

<div id="main" class={theme}>
    <div class="header">
        {#if form.reference}
            <span>[{form.reference.id} → {form.id}]</span>
        {:else}
            <span>[{form.id}]</span>
        {/if}

        <span>{formatDateTime(date)}</span>
    </div>
    <div class="header" id="buttons" class:removing>
        <div>{form.creator.name}</div>

        <div id="button">
            <button onclick={() => openInNewWindow(form)}>
                Open {form.formSchema.name}
            </button>
        </div>

        <div id="icons">
            <PanelIcon onclick={duplicate} tooltip="Copy" {theme}>
                <Duplicate />
            </PanelIcon>
            <PanelIcon
                onclick={deleteAnnotation}
                tooltip="Delete"
                disabled={!canEditForm}
                {theme}
            >
                <Trash />
            </PanelIcon>
        </div>
    </div>
    {#if removing}
        <div>
            Deleting annotation {form.id}
        </div>
        <progress max={maxTime} value={progress}></progress>
        <div>
            <button
                onclick={() => {
                    clearInterval(removing);
                    removing = undefined;
                }}
            >
                Cancel
            </button>
        </div>
    {/if}
</div>

<style lang="scss">
    .light {
        background-color: rgba(248, 250, 252, 0.5);
        color: rgb(2 9 65);
        border: 1px solid rgba(0, 0, 0, 0.2);

        button {
            color: rgb(2 9 65);
            border: 1px solid rgba(0, 0, 0, 0.2);
            background-color: rgba(0, 0, 0, 0.01);
        }

        button:hover {
            background-color: rgba(0, 0, 0, 0.05);
        }

        div.header {
            color: rgba(0, 0, 0, 0.6);
        }
    }

    .dark {
        background-color: rgb(0, 0, 0);
        color: rgb(255, 255, 255);
        border: 1px solid rgba(255, 255, 255, 0.3);

        button {
            color: rgba(255, 255, 255, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            background-color: rgba(255, 255, 255, 0.2);
        }

        button:hover {
            background-color: rgba(255, 255, 255, 0.3);
        }

        div.header {
            color: rgba(255, 255, 255, 0.5);
        }
    }

    div {
        display: flex;
    }

    div.removing {
        opacity: 0.5;
    }

    button {
        cursor: pointer;
        padding: 0.2em;
        border-radius: 2px;
        margin: 0.2em;
        text-wrap-mode: nowrap;
    }

    div#main {
        flex-direction: column;
        flex: 1;
        border-radius: 1px;
        margin-bottom: 0.5em;
        padding: 0.2em;
        font-size: x-small;
    }

    div.header {
        justify-content: space-between;
        align-items: center;
    }
    div#buttons {
        display: flex;
        align-items: center;
    }
    div#buttons > div {
        flex: 1;
    }
    div#icons {
        display: flex;
        justify-content: right;
    }
</style>
