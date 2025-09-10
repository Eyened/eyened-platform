<script lang="ts">
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { AbstractImage } from "$lib/webgl/abstractImage";
    import { SegmentationItem } from "$lib/webgl/segmentationItem";
    import { getContext } from "svelte";

    import ImportSegmentation from "../icons/ImportSegmentation.svelte";
    import ImportSegmentationSelector from "./ImportSegmentationSelector.svelte";
    import { Segmentation } from "$lib/datamodel/segmentation.svelte";
    interface Props {
        segmentation: Segmentation;
        image: AbstractImage;
        segmentationItem: SegmentationItem;
    }

    let { segmentation, image, segmentationItem }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const globalContext = getContext<GlobalContext>("globalContext");

    async function importFromOther() {
        globalContext.dialogue = {
            component: ImportSegmentationSelector,
            props: {
                segmentation,
                image,
                resolve: (other: Segmentation) => {
                    const otherSegmentation = image
                        .getSegmentationItem(other)
                        ?.getMask(viewerContext.index);
                    if (otherSegmentation) {
                        segmentationItem?.importOther(
                            viewerContext.index,
                            otherSegmentation,
                        );
                    } else {
                        console.warn(
                            "Import from other: no segmentation found for segmentation",
                            other.id,
                        );
                    }
                },
            },
        };
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main" onclick={importFromOther}>
    <ImportSegmentation size="1.5em" />
    Import
</div>

<style>
    div.main {
        flex-direction: row;
        background-color: rgba(255, 255, 255, 0.1);
        flex: 1;
        padding: 0.2em;
        margin-bottom: 0.2em;
        margin-top: 0.2em;

        font-size: small;
        font-weight: bold;
        
        display: flex;
        align-items: center;
        gap: 0.5em;
        cursor: pointer !important;
    }
    div.main:hover {
        background-color: rgba(255, 255, 255, 0.2);
        
    }
</style>
