<script lang="ts">
    import { AbstractImage } from "$lib/webgl/abstractImage";
    import { Duplicate } from "../icons/icons";
    import { getContext } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { type DrawingArray, type Mask } from "$lib/webgl/mask.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { SegmentationItem } from "$lib/webgl/segmentationItem";
    import {
        Segmentation,
        type DataRepresentation,
        type Datatype,
        type SimpleDataRepresentation,
    } from "$lib/datamodel/segmentation.svelte";
    import { NPYArray } from "$lib/utils/npy_loader";
    interface Props {
        segmentation: Segmentation;
        image: AbstractImage;
        segmentationItem: SegmentationItem;
    }
    import { convert } from "$lib/webgl/segmentationConverter";

    let { segmentation, image, segmentationItem }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const { creator } = globalContext;

    let duplicateVolume = $state(false);

    const types: Record<"Q" | "B" | "P", SimpleDataRepresentation> = {
        Q: "DualBitMask",
        B: "Binary",
        P: "Probability",
    };
    let type = $state<"Q" | "B" | "P">("Q");
    type = Object.keys(types).find(
        (t) => types[t as "Q" | "B" | "P"] == segmentation.dataRepresentation,
    ) as "Q" | "B" | "P";

    function createArray(
        shape: [number, number, number],
        dataType: Datatype,
    ): NPYArray {
        const n = shape[0] * shape[1] * shape[2];
        let a: DrawingArray;
        if (dataType == "R8UI" || dataType == "R8") {
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

    function copyMaskData(
        indices: number[],
        segmentationItem: SegmentationItem,
        segmentation: Segmentation,
        dataRepresentation: DataRepresentation,
        array: NPYArray,
        image: AbstractImage
    ) {
        for (let i = 0; i < indices.length; i++) {
            const mask = segmentationItem.getMask(indices[i]);
            if (mask) {
                const data = mask.exportData();
                const threshold = 255 * (segmentation.threshold ?? 0.5);
                const dataConverted = convert(
                    data,
                    segmentation.dataRepresentation as SimpleDataRepresentation,
                    dataRepresentation as SimpleDataRepresentation,
                    threshold,
                );
                array.data.set(
                    dataConverted,
                    i * image.height * image.width,
                );
            }
        }
    }

    async function duplicate() {
        globalContext.dialogue = `Duplicating segmentation ${segmentation.id}...`;

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

        let dataType = segmentation.dataType;
        if (dataRepresentation == "Probability") {
            dataType = "R8";
        }
        const item = {
            ...segmentation,
            dataRepresentation,
            dataType,
            // properties that need to be mentioned explicitly, because they're marked with $state and hence not enumerable
            referenceId: segmentation.referenceId,
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

        const array = createArray(
            [depth, image.height, image.width],
            segmentation.dataType,
        );
        if (image.image_id.endsWith("proj")) {
            array.shape = [image.height, 1, image.width];
        }

        if (item.scanIndices) {
            // sparse volume
            copyMaskData(
                item.scanIndices,
                segmentationItem,
                segmentation,
                dataRepresentation,
                array,
                image
            );
        } else {
            // full volume
            const indices = Array.from({ length: depth }, (_, i) => i);
            copyMaskData(
                indices,
                segmentationItem,
                segmentation,
                dataRepresentation,
                array,
                image
            );
        }
        const newSegmentation = await Segmentation.create(item, array);
        console.log("newSegmentation", newSegmentation);

        globalContext.dialogue = null;
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
