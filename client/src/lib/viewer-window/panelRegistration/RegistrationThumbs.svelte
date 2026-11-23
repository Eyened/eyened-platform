<script lang="ts">
    import { getThumbUrl } from "$lib/data-loading/utils";
    import type { ImageGET } from "../../../types/openapi_types";
    import type { OpenImage } from "./groupOpenImages";

    interface Props {
        label: string;
        images: OpenImage[];
        selectedIds: readonly string[];
        ariaRole: string;
        onSelect: (imageId: string) => void;
        children?: import("svelte").Snippet;
    }

    const { label, images, selectedIds, ariaRole, onSelect, children }: Props =
        $props();
</script>

<div class="role">
    <div class="role-label">{label}</div>
    <div class="thumbs">
        {#each images as image (image.imageId)}
            <button
                type="button"
                class="thumb"
                class:selected={selectedIds.includes(image.imageId)}
                title={image.instanceId}
                aria-label="{ariaRole} {image.instanceId}"
                onclick={() => onSelect(image.imageId)}
            >
                <img
                    src={getThumbUrl({ id: image.instanceId } as ImageGET, 144)}
                    alt=""
                    draggable="false"
                />
            </button>
        {/each}
    </div>
    {@render children?.()}
</div>

<style>
    .role {
        margin-top: 0.45em;
    }
    .role-label {
        font-size: 0.75em;
        opacity: 0.8;
        margin-bottom: 0.25em;
    }
    .thumbs {
        display: flex;
        flex-direction: row;
        gap: 0.35em;
        overflow-x: auto;
    }
    button.thumb {
        flex: 0 0 auto;
        margin-top: 0;
        padding: 0;
        border: 2px solid transparent;
        background: black;
        cursor: pointer;
        line-height: 0;
    }
    button.thumb.selected {
        border-color: white;
    }
    button.thumb img {
        width: 3.2rem;
        height: 3.2rem;
        object-fit: contain;
        display: block;
    }
</style>
