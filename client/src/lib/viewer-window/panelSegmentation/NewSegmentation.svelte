<script lang="ts">
    import { getContext } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { Writable } from "svelte/store";
    import FeatureSelect from "./FeatureSelect.svelte";
    import { data } from "$lib/datamodel/model";
    import type { Feature } from "$lib/datamodel/feature.svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

    import { AnnotationType } from "$lib/datamodel/annotationType.svelte";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import { Annotation } from "$lib/datamodel/annotation.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const { image } = getContext<ViewerContext>("viewerContext");
    const { creator } = globalContext;
    const segmentationOverlay = getContext<SegmentationOverlay>(
        "segmentationOverlay",
    );
    const segmentationContext = segmentationOverlay.segmentationContext;
    const { annotationTypes, features, annotationTypeFeatures } = data;

    const qType = annotationTypes.find(
        (t) => t.name == "Binary + Questionable",
    )!;
    const bType = annotationTypes.find((t) => t.name == "Binary")!;
    const pType = annotationTypes.find(
        (t) => t.name == "Probability" && t.dataType == "R8",
    )!;

    const dialogue = getContext<Writable<any>>("dialogue");

    let selectedFeature: Feature | undefined = $state(undefined);

    async function create(
        feature: Feature,
        annotationType: AnnotationType | string,
    ) {
        if (annotationType instanceof AnnotationType) {
            // already an annotation type
        } else if (annotationType == "Q") {
            annotationType = qType;
        } else if (annotationType == "B") {
            annotationType = bType;
        } else if (annotationType == "P") {
            annotationType = pType;
        } else {
            throw new Error(`Unsupported type: ${annotationType}`);
        }
        dialogue.set(`Creating annotation...`);

        await Annotation.createFrom(
            image.instance,
            feature,
            creator,
            annotationType,
        );
        segmentationContext.hideCreators.delete(creator);
        dialogue.set(undefined);
    }

    // let selectList: { [name: string]: Feature[] } = $state({});
    // function selectFeatures(featureSet: { [name: string]: string[] }) {
    //     for (const [groupname, featurenames] of Object.entries(featureSet)) {
    //         selectList[groupname] = [];
    //         for (const name of featurenames) {
    //             const feature = features.find((f) => f.name == name);
    //             if (feature) {
    //                 selectList[groupname].push(feature);
    //             }
    //         }
    //     }
    // }
    // if (image.is3D) {
    //     selectFeatures(featureSetOCT);
    // } else {
    //     selectFeatures(featureSetColorFundus);
    // }
    const availableFeatures = features.filter((f) => {
        // TODO: filter features that are not available for the current image?
        return true;
    });

    function createAnnotationTypeFeatures(dataRepresentation: string) {
        return annotationTypeFeatures
            .filter((f) => {
                return (
                    f.featureIndex == -1 &&
                    f.annotationType.dataRepresentation == dataRepresentation
                );
            })
            .map((f) => {
                return {
                    name: f.annotationType.name,
                    feature: f.feature,
                    annotationType: f.annotationType,
                };
            });
    }

    const multiLabelAnnotationTypeFeatures =
        createAnnotationTypeFeatures("MultiLabel");
    const multiClassAnnotationTypeFeatures =
        createAnnotationTypeFeatures("MultiClass");
    let selectList = false;
</script>

<div class="new">
    {#if selectList}
        <div>
            <select bind:value={selectedFeature}>
                <option value="" selected disabled hidden
                    >Select feature:</option
                >
                {#each Object.entries(selectList) as [groupname, features]}
                    <optgroup label={groupname}>
                        {#each features as feature}
                            <option value={feature}>{feature.name}</option>
                        {/each}
                    </optgroup>
                {/each}
            </select>
            <button
                onclick={() => create(selectedFeature!, qType)}
                disabled={selectedFeature == undefined}
            >
                Create
            </button>
        </div>
    {/if}
    <FeatureSelect
        name="Feature"
        values={availableFeatures}
        types={["Q", "B", "P"]}
        onselect={(feature, type) => create(feature, type)}
    />
    {#if $multiLabelAnnotationTypeFeatures.length > 0}
        <div>
            <ul>
                {#each $multiLabelAnnotationTypeFeatures as item}
                    <li>
                        <button
                            onclick={() =>
                                create(item.feature, item.annotationType)}
                        >
                            {item.name}
                        </button>
                    </li>
                {/each}
            </ul>
        </div>
    {/if}
</div>

<style>
    div {
        display: flex;
    }
    div.new {
        flex-direction: column;
    }
    select {
        width: 10em;
    }
</style>
