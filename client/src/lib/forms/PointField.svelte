<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import { formAnnotations } from "$lib/data";
    import PointImageGroup from "$lib/forms/PointImageGroup.svelte";
    import {
        pointArming,
        FormPointSession,
    } from "$lib/forms/pointArming.svelte";
    import {
        analyzePointSchema,
        getPointsForImage,
        isPointWidget,
        setPointsForImage,
        type ImagePoint,
        type PointList,
    } from "$lib/forms/pointSchema";
    import { deletePointAt } from "$lib/forms/pointMutations";
    import type { JSONSchema } from "$lib/forms/schemaType";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onDestroy } from "svelte";

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

    const seedViewerContext = getContext<ViewerContext | undefined>(
        "viewerContext",
    );
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
    const armKey = $derived(
        `form:${formAnnotationId ?? "unknown"}:${fieldPath}`,
    );
    const armed = $derived(pointArming.session?.key === armKey);
    const liveSession = $derived(armed ? pointArming.session : null);

    const publicId = $derived(
        seedViewerContext?.image.instance.id ?? boundImageId ?? "",
    );

    /** Prefer live session value while armed so chips/labels track the tool. */
    const displayValue = $derived(liveSession ? liveSession.fieldValue : value);

    type PointRow = { publicId: string; index: number; pt: ImagePoint };

    const pointRows = $derived.by((): PointRow[] => {
        if (!analysis) return [];
        if (analysis.storageMode === "bare") {
            const pid = publicId || boundImageId || "";
            if (!pid) return [];
            return getPointsForImage(displayValue, pid, analysis).flatMap(
                (pt, index) => (pt ? [{ publicId: pid, index, pt }] : []),
            );
        }
        const ids: string[] = [];
        if (
            displayValue &&
            typeof displayValue === "object" &&
            !Array.isArray(displayValue)
        ) {
            for (const key of Object.keys(
                displayValue as Record<string, unknown>,
            )) {
                if (!ids.includes(key)) ids.push(key);
            }
        }
        if (publicId && !ids.includes(publicId)) ids.push(publicId);
        const rows: PointRow[] = [];
        for (const id of ids.sort()) {
            for (const [index, pt] of getPointsForImage(
                displayValue,
                id,
                analysis,
            ).entries()) {
                if (pt) rows.push({ publicId: id, index, pt });
            }
        }
        return rows;
    });

    type ImageGroup = { publicId: string; rows: PointRow[] };

    const imageGroups = $derived.by((): ImageGroup[] => {
        const byId: Record<string, PointRow[]> = {};
        for (const row of pointRows) {
            (byId[row.publicId] ??= []).push(row);
        }
        return Object.entries(byId).map(([pid, rows]) => ({
            publicId: pid,
            rows,
        }));
    });

    /** Show i only when this point carries an OCT index (number or explicit null). */
    function indexApplicable(pt: ImagePoint): boolean {
        return "index" in pt;
    }

    function formatCoord(pt: ImagePoint): string {
        const x = Math.round(pt.x);
        const y = Math.round(pt.y);
        if (!indexApplicable(pt)) return `[${x},${y}]`;
        if (typeof pt.index === "number") {
            return `[${x},${y},${Math.round(pt.index)}]`;
        }
        return `[${x},${y},null]`;
    }

    function extraPreview(pt: ImagePoint): string {
        if (!analysis) return "";
        const parts: string[] = [];
        for (const extra of analysis.enumExtras) {
            const v = pt[extra.key];
            if (typeof v === "string" && v.length) parts.push(v);
        }
        for (const [key, prop] of Object.entries(
            analysis.pointObjectSchema.properties ?? {},
        )) {
            if (
                key === "x" ||
                key === "y" ||
                key === "index" ||
                analysis.enumExtras.some((e) => e.key === key)
            ) {
                continue;
            }
            if (prop.type === "string") {
                const v = pt[key];
                if (typeof v === "string" && v.length) parts.push(v);
            }
        }
        return parts.length ? ` ${parts.join(", ")}` : "";
    }

    const stringExtraKeys = $derived.by(() => {
        if (!analysis) return [] as string[];
        return Object.entries(analysis.pointObjectSchema.properties ?? {})
            .filter(
                ([key, prop]) =>
                    key !== "x" &&
                    key !== "y" &&
                    key !== "index" &&
                    !analysis.enumExtras.some((e) => e.key === key) &&
                    prop.type === "string",
            )
            .map(([key]) => key);
    });

    const hasExtras = $derived(
        !!analysis &&
            (analysis.enumExtras.length > 0 || stringExtraKeys.length > 0),
    );

    let expandedKey = $state<string | null>(null);

    function rowKey(row: PointRow) {
        return `${row.publicId}:${row.index}`;
    }

    function toggleExpand(row: PointRow) {
        const key = rowKey(row);
        expandedKey = expandedKey === key ? null : key;
    }

    const canActivate = $derived(!!(canEdit && analysis && seedViewerContext));

    function toggleActivate() {
        if (!analysis || !seedViewerContext) return;
        pointArming.arm(
            new FormPointSession({
                key: armKey,
                canEdit,
                pointStyle: pointMarker.style,
                radius: pointMarker.radius,
                color: pointMarker.color,
                label: schema.title || fieldPath,
                analysis,
                initialValue: value,
                setFieldValue: (next) => onchange(next),
            }),
        );
    }

    function clear() {
        if (!analysis) {
            onchange(undefined);
            return;
        }
        if (analysis.storageMode === "byPublicId") {
            if (liveSession) {
                liveSession.fieldValue = {};
                liveSession.persist();
            } else {
                onchange({});
            }
        } else {
            const pid = publicId || boundImageId || "";
            if (liveSession) {
                liveSession.setPoints(pid, []);
                liveSession.persist();
            } else {
                onchange(setPointsForImage(value, pid, [], analysis));
            }
        }
        expandedKey = null;
        if (armed) pointArming.disarm(armKey);
    }

    // Unmount MainViewer PointTools when this annotation is deleted or the field unmounts.
    $effect(() => {
        if (formAnnotationId == null) return;
        if (!formAnnotations.has(formAnnotationId)) {
            pointArming.disarm(armKey);
        }
    });

    onDestroy(() => {
        pointArming.disarm(armKey);
    });

    function commitPoints(pid: string, pts: PointList) {
        if (!analysis) return;
        if (liveSession) {
            liveSession.setPoints(pid, pts);
            liveSession.persist();
            return;
        }
        onchange(setPointsForImage(value, pid, pts, analysis));
    }

    function pointsFor(pid: string) {
        if (!analysis) return [] as PointList;
        if (liveSession) return liveSession.getPoints(pid);
        return getPointsForImage(value, pid, analysis);
    }

    function updatePointExtra(
        pid: string,
        index: number,
        key: string,
        extraValue: string,
    ) {
        const pts = [...pointsFor(pid)];
        const pt = pts[index];
        if (!pt) return;
        pts[index] = { ...pt, [key]: extraValue };
        commitPoints(pid, pts);
    }

    function updatePointCoord(
        pid: string,
        index: number,
        key: "x" | "y" | "index",
        raw: string,
    ) {
        const pts = [...pointsFor(pid)];
        const pt = pts[index];
        if (!pt) return;
        if (key === "index" && raw.trim() === "") {
            pts[index] = { ...pt, index: null };
            commitPoints(pid, pts);
            return;
        }
        const n = Number(raw);
        if (!Number.isFinite(n)) return;
        pts[index] = { ...pt, [key]: n };
        commitPoints(pid, pts);
    }

    function removePoint(pid: string, index: number) {
        if (!analysis) return;
        commitPoints(
            pid,
            deletePointAt(pointsFor(pid), index, analysis.registrationMode),
        );
        expandedKey = null;
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
        <div class="actions">
            {#if seedViewerContext}
                <Button
                    variant={armed ? "default" : "outline"}
                    size="sm"
                    disabled={!canActivate}
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
                    disabled={pointRows.length === 0}
                >
                    Clear
                </Button>
            {/if}
        </div>

        {#if imageGroups.length === 0}
            <div class="empty">no points</div>
        {:else}
            {#each imageGroups as group (group.publicId)}
                <PointImageGroup
                    {group}
                    storageMode={analysis.storageMode}
                    {expandedKey}
                    {canEdit}
                    {hasExtras}
                    enumExtras={analysis.enumExtras}
                    {stringExtraKeys}
                    {formatCoord}
                    {extraPreview}
                    {rowKey}
                    {indexApplicable}
                    onToggleExpand={toggleExpand}
                    onUpdateCoord={updatePointCoord}
                    onUpdateExtra={updatePointExtra}
                    onRemovePoint={removePoint}
                    onCollapse={() => (expandedKey = null)}
                />
            {/each}
        {/if}
    {/if}
</div>

<style>
    .point-field {
        display: flex;
        flex-direction: column;
        gap: 0.4em;
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
    .actions {
        display: flex;
        flex-direction: row;
        gap: 0.5em;
        align-items: center;
    }
    .hint,
    .warn,
    .empty {
        font-size: 0.85em;
        color: #a60;
    }
    .warn {
        color: #a00;
    }
    .empty {
        font-family: monospace;
        opacity: 0.7;
        color: inherit;
    }
</style>
