<script lang="ts">
    import { AbstractImage } from "$lib/webgl/abstractImage";
    import { Duplicate } from "../icons/icons";
    import { dialogueManager } from "$lib/dialogue/DialogueManager";
    import { getContext } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { type DrawingArray, type Mask } from "$lib/webgl/Mask";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { SegmentationItem } from "$lib/webgl/segmentationItem";
    import {
        Segmentation,
        type DataRepresentation,
        type Datatype,
    } from "$lib/datamodel/segmentation.svelte";
    import { NPYArray } from "$lib/utils/npy_loader";
    interface Props {
        segmentation: Segmentation;
        image: AbstractImage;
        segmentationItem: SegmentationItem;
        mask: Mask;
    }

    let { segmentation, image, segmentationItem, mask }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { creator } = getContext<GlobalContext>("globalContext");

    let duplicateVolume = $state(false);

    const types: Record<"Q" | "B" | "P", DataRepresentation> = {
        Q: "DualBitMask",
        B: "Binary",
        P: "Probability",
    };
    let type = $state<"Q" | "B" | "P">("Q");
    type = Object.keys(types).find(
        (t) => types[t as "Q" | "B" | "P"] == segmentation.dataRepresentation,
    ) as "Q" | "B" | "P";


    function createArray(shape: [number, number, number], dataType: Datatype): NPYArray {
        const n = shape[0] * shape[1] * shape[2];
        let a: DrawingArray;
        if (dataType == "R8UI") {
            a = new Uint8Array(n);
        } else if (dataType == "R16UI") {
            a = new Uint16Array(n);
        } else if (dataType == "R32UI") {
            a = new Uint32Array(n);
        } else if (dataType == "R32F") {
            a = new Float32Array(n);
        } else {
            throw new Error(`Unsupported data type: ${dataType}`);
        }
        return new NPYArray(a, shape, false);
    }

    async function duplicate() {
        dialogueManager.showQuery(
            `Duplicating segmentation ${segmentation.id}...`,
        );

        let dataRepresentation: DataRepresentation;
        if (
            segmentation.dataRepresentation == "MultiClass" ||
            segmentation.dataRepresentation == "MultiLabel"
        ) {
            // same as original annotation type
            dataRepresentation = segmentation.dataRepresentation;
        } else {
            // new annotation can be of different type
            dataRepresentation = types[type];
        }

        const item = {
            ...segmentation,
            dataRepresentation: dataRepresentation,

            // properties that need to be mentioned explicitly, because they're marked with $state and hence not enumerable
            referenceSegmentationId: segmentation.referenceId,
            scanIndices: segmentation.scanIndices,
            threshold: segmentation.threshold,

            // overwrite creatorId to current user
            creatorId: creator.id,
        };

        const scanNr = viewerContext.index;
        
        let depth = 1;
        if (duplicateVolume) {
            if (segmentation.scanIndices) {
                // only upload the data for active scan indices
                depth = segmentation.scanIndices.length;
            } else {
                // upload the full volume                
                depth = image.depth;
            }
        } else if (image.is3D) {
            // only duplicate the current scan
            item.scanIndices = [scanNr];
        } 

        const array = createArray([depth, image.height, image.width], segmentation.dataType);
        if (image.image_id.endsWith('proj')) {
            array.shape = [image.height, 1, image.width];
        }

        if (item.scanIndices) {
            // sparse volume 
            for (let i = 0; i < item.scanIndices.length; i++) {
                const mask = segmentationItem.getMask(item.scanIndices[i]);
                if (mask) {
                    array.data.set(mask.exportData(), i * image.height * image.width);
                }
            }
        } else {
            // full volume
            for (let i = 0; i < depth; i++) {
                const mask = segmentationItem.getMask(i);
                if (mask) {
                    array.data.set(mask.exportData(), i * image.height * image.width);
                }
            }
        }            
        const newSegmentation = await Segmentation.create(item, array);
        console.log('newSegmentation',newSegmentation);

        dialogueManager.hide();
    }
</script>

<div class="main">
    <h3><Duplicate size="1.5em" />Duplicate</h3>

    {#if image.is3D}
        <div>
            <label>
                <input type="radio" bind:group={duplicateVolume} value={true} />
                Volume
            </label>
            <label>
                <input
                    type="radio"
                    bind:group={duplicateVolume}
                    value={false}
                />
                B-scan
            </label>
        </div>
    {/if}
    {#if segmentation.dataRepresentation == "MultiClass" || segmentation.dataRepresentation == "MultiLabel"}{:else}
        <div>
            <label>
                <input type="radio" bind:group={type} value="Q" />
                Q
            </label>
            <label>
                <input type="radio" bind:group={type} value="B" />
                B
            </label>
            <label>
                <input type="radio" bind:group={type} value="P" />
                P
            </label>
        </div>
    {/if}
    <button onclick={duplicate}>Create copy</button>
</div>

<style>
    div.main {
        flex-direction: column;
        background-color: rgba(255, 255, 255, 0.1);
        flex: 1;
        padding: 0.2em;
        margin-bottom: 0.2em;
        margin-top: 0.2em;
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
