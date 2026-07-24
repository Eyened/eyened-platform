<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import { Input } from "$lib/components/ui/input";
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import {
        analyzePointSchema,
        getPointsForImage,
        isPointWidget,
        setPointsForImage,
        type ImagePoint,
    } from "$lib/forms/pointSchema";
    import type { JSONSchema } from "$lib/forms/schemaType";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool";
    import { getContext } from "svelte";

    interface Props {
        schema: JSONSchema;
        value: unknown;
        onchange: (value: unknown) => void;
        canEdit?: boolean;
        entityType?: string | null;
        fieldPath?: string;
    }

    let {
        schema,
        value,
        onchange,
        canEdit = true,
        entityType = "ImageInstance",
        fieldPath = "point",
    }: Props = $props();

    const viewerContext = getContext<ViewerContext | undefined>("viewerContext");
    const formAnnotationId = getContext<number | undefined>(
        "pointFormAnnotationId",
    );
    const boundImageId = getContext<string | undefined>("pointBoundImageId");
    const taskContext = getContext<TaskContext | undefined>("taskContext");

    const pointMarker = $derived(
        mergeClientConfig(
            CLIENT_DEFAULTS,
            taskContext?.task.task_definition.config,
        ).point_marker,
    );

    const analysis = $derived(analyzePointSchema(schema, entityType));
    const publicId = $derived(viewerContext?.image.instance.id ?? "");
    const armKey = $derived(
        `form:${formAnnotationId ?? "unknown"}:${fieldPath}`,
    );
    const armed = $derived(pointArming.isArmed(armKey));

    const pointsOnImage = $derived(
        analysis
            ? getPointsForImage(value, publicId, analysis)
            : ([] as (ImagePoint | null)[]),
    );

    const summary = $derived.by(() => {
        if (!analysis) return "Invalid point schema";
        const placed = pointsOnImage.filter((p) => p != null);
        if (analysis.cardinality === "single") {
            const p = placed[0];
            return p
                ? `(${p.x.toFixed(1)}, ${p.y.toFixed(1)})`
                : "no point";
        }
        return `${placed.length} point(s)` + (publicId ? ` on ${publicId}` : "");
    });

    const canActivate = $derived(
        !!(canEdit && viewerContext && analysis && publicId),
    );

    const imageMismatch = $derived.by(() => {
        if (!viewerContext || !analysis) return false;
        if (analysis.storageMode !== "bare") return false;
        if (!boundImageId) return false;
        return boundImageId !== publicId;
    });

    function toggleActivate() {
        if (!viewerContext || !analysis) return;
        if (imageMismatch) return;

        pointArming.arm(armKey, () => {
            const tool = new PointTool({
                canEdit,
                analysis,
                label: schema.title || fieldPath,
                pointStyle: pointMarker.style,
                radius: pointMarker.radius,
                color: pointMarker.color,
                getPublicId: () => viewerContext.image.instance.id,
                getFieldValue: () => value,
                setFieldValue: (next) => onchange(next),
            });
            const remove = viewerContext.addOverlay(tool);
            return () => {
                tool.destroy();
                remove();
            };
        });
    }

    function clear() {
        if (!analysis) {
            onchange(undefined);
            return;
        }
        const pid = viewerContext?.image.instance.id ?? publicId;
        onchange(setPointsForImage(value, pid, [], analysis));
        if (armed) pointArming.disarm(armKey);
    }

    function updatePointExtra(index: number, key: string, extraValue: string) {
        if (!analysis) return;
        const pts = [...pointsOnImage];
        const pt = pts[index];
        if (!pt) return;
        pts[index] = { ...pt, [key]: extraValue };
        onchange(setPointsForImage(value, publicId, pts, analysis));
    }
</script>

<div class="point-field">
    <div class="header">
        <span class="title">{schema.title || fieldPath}</span>
        {#if schema.description}
            <span class="desc">{schema.description}</span>
        {/if}
    </div>

    {#if !isPointWidget(schema) || !analysis}
        <p class="warn">Point widget misconfigured for this schema.</p>
    {:else}
        <div class="summary">{summary}</div>

        {#if imageMismatch}
            <p class="hint">
                Viewer image differs from this form's image — point edits
                disabled.
            </p>
        {/if}

        <div class="actions">
            {#if viewerContext}
                <Button
                    variant={armed ? "default" : "outline"}
                    size="sm"
                    disabled={!canActivate || imageMismatch}
                    onclick={toggleActivate}
                >
                    {armed ? "Deactivate tool" : "Activate tool"}
                </Button>
            {:else}
                <span class="hint">No viewer — tool unavailable</span>
            {/if}
            {#if canEdit}
                <Button
                    variant="outline"
                    size="sm"
                    onclick={clear}
                    disabled={pointsOnImage.every((p) => p == null)}
                >
                    Clear
                </Button>
            {/if}
        </div>

        {#each pointsOnImage as pt, i}
            {#if pt}
                <div class="extras">
                    {#if analysis.cardinality === "list"}
                        <span class="idx">{i}</span>
                    {/if}
                    {#each analysis.enumExtras as extra}
                        <label>
                            {extra.key}
                            <select
                                disabled={!canEdit}
                                value={String(pt[extra.key] ?? "")}
                                onchange={(e) =>
                                    updatePointExtra(
                                        i,
                                        extra.key,
                                        (e.currentTarget as HTMLSelectElement)
                                            .value,
                                    )}
                            >
                                <option value="">—</option>
                                {#each extra.values as opt}
                                    <option value={opt}>{opt}</option>
                                {/each}
                            </select>
                        </label>
                    {/each}
                    {#each Object.entries(analysis.pointObjectSchema.properties ?? {}) as [key, prop]}
                        {#if key !== "x" && key !== "y" && !analysis.enumExtras.some((e) => e.key === key) && prop.type === "string"}
                            <label>
                                {key}
                                <Input
                                    disabled={!canEdit}
                                    value={String(pt[key] ?? "")}
                                    oninput={(e) =>
                                        updatePointExtra(
                                            i,
                                            key,
                                            (e.currentTarget as HTMLInputElement)
                                                .value,
                                        )}
                                    class="min-w-[120px]"
                                />
                            </label>
                        {/if}
                    {/each}
                </div>
            {/if}
        {/each}
    {/if}
</div>

<style>
    .point-field {
        display: flex;
        flex-direction: column;
        gap: 0.35em;
        padding: 0.25em;
    }
    .header {
        display: flex;
        flex-direction: column;
        gap: 0.15em;
    }
    .title {
        font-weight: bold;
    }
    .desc {
        font-size: 0.9em;
        opacity: 0.8;
    }
    .summary {
        font-family: monospace;
        font-size: 0.9em;
    }
    .actions {
        display: flex;
        flex-direction: row;
        gap: 0.5em;
        align-items: center;
    }
    .hint,
    .warn {
        font-size: 0.85em;
        color: #a60;
    }
    .warn {
        color: #a00;
    }
    .extras {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5em;
        align-items: center;
    }
    .idx {
        font-family: monospace;
        opacity: 0.6;
    }
    label {
        display: flex;
        align-items: center;
        gap: 0.25em;
        font-size: 0.85em;
    }
</style>
