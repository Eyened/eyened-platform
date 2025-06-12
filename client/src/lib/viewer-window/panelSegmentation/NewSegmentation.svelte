<script lang="ts">
    import { getContext } from "svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { Writable } from "svelte/store";
    import FeatureSelect from "./FeatureSelect.svelte";
    import { data } from "$lib/datamodel/model";
    import type { Feature } from "$lib/datamodel/feature.svelte";
    import { featureSetColorFundus, featureSetOCT } from "$lib/viewer-config";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

    import type { AnnotationType } from "$lib/datamodel/annotationType";
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

    const annotationType = annotationTypes.find((t) => t.name == "R/G mask")!;

    const dialogue = getContext<Writable<DialogueType>>("dialogue");

    let selectedFeature: Feature | undefined = $state(undefined);

    async function create(feature: Feature, annotationType: AnnotationType) {
        dialogue.set(`Creating annotation...`);

        const annotation = await Annotation.createFrom(
            image.instance,
            feature,
            creator,
            annotationType,
        );
        segmentationContext.hideCreators.delete(creator);
        dialogue.set(undefined);
    }

    let selectList: { [name: string]: Feature[] } = $state({});
    function selectFeatures(featureSet: { [name: string]: string[] }) {
        for (const [groupname, featurenames] of Object.entries(featureSet)) {
            selectList[groupname] = [];
            for (const name of featurenames) {
                const feature = features.find((f) => f.name == name);
                if (feature) {
                    selectList[groupname].push(feature);
                }
            }
        }
    }
    if (image.is3D) {
        selectFeatures(featureSetOCT);
    } else {
        selectFeatures(featureSetColorFundus);
    }
    const availableFeatures = features.filter((f) => {
        // TODO: filter features that are not available for the current image?
        return true;
    }).$;

    const multiLabelAnnotationTypeFeatures = annotationTypeFeatures.filter(
        (f) => {
            return (
                f.feature_index == -1 &&
                f.annotationType.dataRepresentation == "MULTI_LABEL"
            );
        },
    ).$;
    const multiLabelFeatures = multiLabelAnnotationTypeFeatures.map(
        (f) => f.feature,
    );
    const multiLabelFeaturesMapping = new Map(
        multiLabelAnnotationTypeFeatures.map((f) => [
            f.feature,
            f.annotationType,
        ]),
    );
</script>

<div class="new">
    <div>
        <select bind:value={selectedFeature}>
            <option value="" selected disabled hidden>Select feature:</option>
            {#each Object.entries(selectList) as [groupname, features]}
                <optgroup label={groupname}>
                    {#each features as feature}
                        <option value={feature}>{feature.name}</option>
                    {/each}
                </optgroup>
            {/each}
        </select>
        <button
            onclick={() => create(selectedFeature!, annotationType)}
            disabled={selectedFeature == undefined}
        >
            Create
        </button>
    </div>

    <span> R/G mask </span>
    <FeatureSelect
        values={availableFeatures}
        onselect={(feature) => create(feature, annotationType)}
    />
    <span> Multi-label </span>
    <FeatureSelect
        values={multiLabelFeatures}
        onselect={(feature) =>
            create(feature, multiLabelFeaturesMapping.get(feature)!)}
    />
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
