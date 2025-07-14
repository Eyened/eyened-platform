<script lang="ts">
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { Annotation } from "$lib/datamodel/annotation.svelte";
    import { dialogueManager } from "$lib/dialogue/DialogueManager";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { AbstractImage } from "$lib/webgl/abstractImage";
    import { ProbabilitySegmentation } from "$lib/webgl/segmentation";
    import { SegmentationItem } from "$lib/webgl/segmentationItem";
    import { getContext } from "svelte";
    import { Duplicate, PanelIcon } from "../icons/icons";
    import ImportSegmentation from "../icons/ImportSegmentation.svelte";
    import ImportSegmentationSelector from "./ImportSegmentationSelector.svelte";
    interface Props {
        annotation: Annotation;
        image: AbstractImage;
        segmentationItem: SegmentationItem;
    }

    let { annotation, image, segmentationItem }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { creator } = getContext<GlobalContext>("globalContext");

    let duplicateVolume = $state(false);
    async function importFromOther() {
        dialogueManager.show(
            ImportSegmentationSelector,
            {
                annotation,
                image,
            },
            (other: Annotation) => {
                const otherSegmentation = image
                    .getSegmentationItem(other)
                    ?.getSegmentation(viewerContext.index);
                if (otherSegmentation) {
                    segmentationItem?.importOther(
                        viewerContext.index,
                        otherSegmentation,
                    );
                } else {
                    console.warn(
                        "Import from other: no segmentation found for annotation",
                        other.id,
                    );
                }
            },
        );
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main" onclick={importFromOther}>
    <h3><ImportSegmentation size="1.5em" />Import</h3>
</div>

<style>
    div.main {
        flex-direction: column;
        background-color: rgba(255, 255, 255, 0.1);
        flex: 1;
        padding: 0.2em;
        margin-bottom: 0.2em;
        margin-top: 0.2em;
        cursor: pointer;
    }
    h3 {
        font-size: small;
        font-weight: bold;
        margin: 0;
        padding: 0;
        display: flex;
        align-items: center;
        gap: 0.5em;
    }
</style>
