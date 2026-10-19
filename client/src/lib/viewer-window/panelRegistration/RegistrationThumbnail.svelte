<script lang="ts">
    import type { PointMarkerConfig } from "$lib/config/clientDefaults";
    import type { JSONSchema } from "$lib/forms/schemaType";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext, setContext, untrack } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import { bindRegistrationPointTool } from "./bindRegistrationPointTool";

    interface Props {
        image: AbstractImage;
        annotationId: number;
        schema: JSONSchema;
        canEdit: boolean;
        pointMarker: PointMarkerConfig;
    }

    let { image, annotationId, schema, canEdit, pointMarker }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    const viewerContext = new ViewerContext(
        untrack(() => image),
        viewerWindowContext,
    );
    setContext("viewerContext", viewerContext);

    // Point writes update formAnnotations. Reading that store inside the
    // effect would tear down the tool on every drag, so only the bind inputs
    // are tracked.
    $effect(() => {
        const nextAnnotationId = annotationId;
        const nextSchema = schema;
        const nextCanEdit = canEdit;
        const nextMarker = pointMarker;
        return untrack(() =>
            bindRegistrationPointTool({
                viewerContext,
                annotationId: nextAnnotationId,
                schema: nextSchema,
                canEdit: nextCanEdit,
                pointMarker: nextMarker,
            }),
        );
    });
</script>

<div class="thumb">
    <Viewer showInfo={false} foreground />
</div>

<style>
    .thumb {
        flex: 1;
        min-width: 0;
        display: flex;
        position: relative;
    }
</style>
