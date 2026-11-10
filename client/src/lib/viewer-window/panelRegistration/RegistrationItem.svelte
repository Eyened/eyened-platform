<script lang="ts">
    import type { FormAnnotationGET } from "../../../types/openapi_types";
    import { PanelIcon, Trash } from "../icons/icons";

    interface Props {
        formAnnotation: FormAnnotationGET;
        active: boolean;
        onactivate: (annotation: FormAnnotationGET) => void;
        onremove: (annotation: FormAnnotationGET) => void;
    }
    let { formAnnotation, active, onactivate, onremove }: Props = $props();
</script>

<li class="outer" class:active>
    <button
        type="button"
        class="info"
        onclick={() => onactivate(formAnnotation)}
    >
        <span class="creator">{formAnnotation.creator.name}</span>
        <span class="annotationID">[{formAnnotation.id}]</span>
    </button>
    <PanelIcon
        onclick={() => onremove(formAnnotation)}
        tooltip="Remove"
        Icon={Trash}
    />
</li>

<style>
    li.outer {
        display: flex;
        align-items: center;
        cursor: pointer;
        background-color: rgba(255, 255, 255, 0.1);
        padding-left: 0.5em;
        margin-bottom: 0.1em;
        border-radius: 1px;
    }
    li.outer:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }
    li.outer.active {
        background-color: rgb(57, 158, 165);
        color: white;
    }
    .info {
        display: flex;
        align-items: center;
        flex: 1 1 auto;
        min-width: 0;
        gap: 0.35em;
        background: none;
        border: 0;
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;
        padding: 0.15em 0;
    }
    .creator {
        flex: 1;
    }
    .annotationID {
        color: rgba(255, 255, 255, 0.4);
    }
</style>
