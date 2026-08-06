<script lang="ts">
    import CopyIconButton from "$lib/components/CopyIconButton.svelte";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { EnfaceProjectionOverlay } from "$lib/viewer/overlays/EnfaceProjectionOverlay";
    import type { EnfaceProjectionMode } from "$lib/viewer/viewer-utils";
    import { OCTLinesOverlay } from "$lib/viewer/overlays/OCTLinesOverlays";
    import { getContext, setContext } from "svelte";
    import type { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import MainIcon from "./icons/MainIcon.svelte";
    import Lines from "./icons/Lines.svelte";
    import EnfaceProjectionModeIcon from "./icons/EnfaceProjectionModeIcon.svelte";
    import { resolveEnfaceOverlaySources } from "$lib/registration/resolveEnfaceOverlaySources";
    import { instances } from "$lib/data/stores.svelte";

    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const publicId = $derived(image.instance.id);

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const viewerContext = viewerWindowContext.topViewers.get(image)!;
    setContext("viewerContext", viewerContext);

    const isProjImage = $derived(image.image_id.endsWith("_proj"));
    // Photo locators and patient-level registration sets keep importing after this
    // viewer mounts, so the overlay sources have to re-resolve on every bump.
    const registrationRevision = $derived(
        viewerWindowContext.registration.revision,
    );
    const resolved = $derived.by(() =>
        resolveEnfaceOverlaySources({
            imageId: image.image_id,
            imageWidth: image.width,
            imageHeight: image.height,
            registration: viewerWindowContext.registration,
            registrationRevision,
            managers: viewerWindowContext.enfaceProjectionManagers,
            getImageSize: (id) => {
                for (const [img] of viewerWindowContext.topViewers) {
                    if (img.image_id === id) {
                        return [img.width, img.height];
                    }
                }
                if (id.endsWith("_proj")) {
                    const octId = id.slice(0, -"_proj".length);
                    const mgr =
                        viewerWindowContext.enfaceProjectionManagers.get(octId);
                    if (mgr) {
                        return [mgr.octImage.width, mgr.octImage.depth];
                    }
                }
                const meta = instances.get(id);
                if (meta) {
                    return [meta.columns, meta.rows];
                }
                return undefined;
            },
            projMode: viewerContext.enfaceProjectionMode,
            linkedModes: viewerContext.enfaceProjectionModesByOct,
        }),
    );
    const paintSources = $derived.by(() =>
        resolved.flatMap((source) => {
            const mainViewerContext = source.manager.mainViewerContext;
            return mainViewerContext ? [{ ...source, mainViewerContext }] : [];
        }),
    );

    let photoLocators = $derived(
        viewerWindowContext.photoLocators.get(image.image_id)!,
    );
    let hasLocators = $derived(
        image.is2D && photoLocators && photoLocators.length,
    );
    let hideLinesOverlay = $state(false);

    const projectionModeLabels: Record<EnfaceProjectionMode, string> = {
        off: "Enface segmentation off",
        binary: "Enface segmentation: mask",
        heatmap: "Enface segmentation: thickness heatmap",
    };

    const projectionModeHoverColors: Record<EnfaceProjectionMode, string> = {
        off: "rgb(175, 175, 175)",
        binary: "white",
        heatmap: "rgb(255, 200, 120)",
    };

    $effect(() => {
        if (hasLocators && !hideLinesOverlay) {
            return viewerContext.addOverlay(new OCTLinesOverlay(photoLocators));
        }
    });

    $effect(() => {
        const sources = paintSources.filter((source) => source.mode !== "off");
        if (!sources.length) {
            return;
        }
        return viewerContext.addOverlay(new EnfaceProjectionOverlay(sources));
    });

    function toggleLinesOverlay(e: MouseEvent) {
        e.stopPropagation();
        hideLinesOverlay = !hideLinesOverlay;
    }

    function cycleProjectionMode(e: MouseEvent) {
        e.stopPropagation();
        const modes: EnfaceProjectionMode[] = ["off", "binary", "heatmap"];
        const index = modes.indexOf(viewerContext.enfaceProjectionMode);
        viewerContext.enfaceProjectionMode = modes[(index + 1) % modes.length];
    }

    function cycleLinkedProjectionMode(e: MouseEvent, octPublicId: string) {
        e.stopPropagation();
        viewerContext.cycleEnfaceProjectionModeForOct(octPublicId);
    }

    function selectImage(e: MouseEvent) {
        if (e.shiftKey) {
            viewerWindowContext.addImagePanel(image);
        } else {
            viewerWindowContext.setImagePanel(image);
        }
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="item" class:wide={image.is3D} onclick={(e) => selectImage(e)}>
    <Viewer showInfo={false} />
    <div class="copy-bar">
        <span class="public-id">{publicId}</span>
        <CopyIconButton text={publicId} ariaLabel="Copy public ID" />
    </div>
    {#if hasLocators || resolved.length > 0}
        <div class="header overlay">
            <div class="content outer">
                <div class="content">
                    {#if isProjImage && resolved.length > 0}
                        <MainIcon
                            onclick={cycleProjectionMode}
                            active={viewerContext.enfaceProjectionMode !==
                                "off"}
                            tooltip={projectionModeLabels[
                                viewerContext.enfaceProjectionMode
                            ]}
                            hoverColor={projectionModeHoverColors[
                                viewerContext.enfaceProjectionMode
                            ]}
                            iconSnippet={projectionModeIcon}
                        />
                    {:else}
                        {#each resolved as source (source.octPublicId)}
                            <MainIcon
                                onclick={(event) =>
                                    cycleLinkedProjectionMode(
                                        event,
                                        source.octPublicId,
                                    )}
                                active={source.mode !== "off"}
                                tooltip={`${projectionModeLabels[source.mode]} (${source.octPublicId})`}
                                hoverColor={projectionModeHoverColors[
                                    source.mode
                                ]}
                            >
                                {#snippet iconSnippet()}
                                    <EnfaceProjectionModeIcon
                                        mode={source.mode}
                                        gradientId={`enface-heatmap-${publicId}-${source.octPublicId}`}
                                    />
                                {/snippet}
                            </MainIcon>
                        {/each}
                    {/if}
                    {#if hasLocators}
                        <MainIcon
                            onclick={toggleLinesOverlay}
                            active={!hideLinesOverlay}
                            Icon={Lines}
                        />
                    {/if}
                </div>
            </div>
        </div>
    {/if}
</div>

{#snippet projectionModeIcon()}
    <EnfaceProjectionModeIcon
        mode={viewerContext.enfaceProjectionMode}
        gradientId="enface-heatmap-{publicId}"
    />
{/snippet}

<style>
    div {
        flex: 1;
        display: flex;
    }
    div.overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        pointer-events: none;
    }
    div.content {
        pointer-events: auto;
        flex: 0;
    }
    div.content.outer {
        flex-direction: column;
    }
    div.item {
        border-bottom: 1px solid gray;
        z-index: 2;
        border-right: 1px solid gray;
        position: relative;
    }
    div.item:hover {
        border-bottom: 1px solid white;
    }
    div.wide {
        flex: 2;
    }
    div.header {
        color: white;
        display: flex;
        margin: 0.5em;
    }
    .copy-bar {
        position: absolute;
        top: 0.5em;
        right: 0.5em;
        z-index: 3;
        display: flex;
        align-items: center;
        gap: 0.15rem;
        max-width: calc(100% - 1em);
        padding: 0.1rem 0.35rem;
        border-radius: 0.15rem;
        background-color: rgb(0 0 0 / 0.55);
        color: rgb(255 255 255 / 0.85);
        font-size: 0.75rem;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.15s ease;
    }
    .item:hover .copy-bar {
        opacity: 1;
        pointer-events: auto;
    }
    .public-id {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
</style>
