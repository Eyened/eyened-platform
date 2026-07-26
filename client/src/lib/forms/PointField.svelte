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
    const armed = $derived(pointArming.armed?.key === armKey);

    const publicId = $derived(
        seedViewerContext?.image.instance.id ?? boundImageId ?? "",
    );

    type PointRow = { publicId: string; index: number; pt: ImagePoint };

    const pointRows = $derived.by((): PointRow[] => {
        if (!analysis) return [];
        if (analysis.storageMode === "bare") {
            const pid = publicId || boundImageId || "";
            if (!pid) return [];
            return getPointsForImage(value, pid, analysis).flatMap((pt, index) =>
                pt ? [{ publicId: pid, index, pt }] : [],
            );
        }
        const ids = new Set<string>();
        if (value && typeof value === "object" && !Array.isArray(value)) {
            for (const key of Object.keys(value as Record<string, unknown>)) {
                ids.add(key);
            }
        }
        if (publicId) ids.add(publicId);
        const rows: PointRow[] = [];
        for (const id of [...ids].sort()) {
            for (const [index, pt] of getPointsForImage(
                value,
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
        const byId = new Map<string, PointRow[]>();
        for (const row of pointRows) {
            const list = byId.get(row.publicId) ?? [];
            list.push(row);
            byId.set(row.publicId, list);
        }
        return [...byId.entries()].map(([pid, rows]) => ({
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
        pointArming.armForm({
            key: armKey,
            analysis,
            label: schema.title || fieldPath,
            canEdit,
            pointStyle: pointMarker.style,
            radius: pointMarker.radius,
            color: pointMarker.color,
            getFieldValue: () => value,
            setFieldValue: (next) => onchange(next),
        });
    }

    function clear() {
        if (!analysis) {
            onchange(undefined);
            return;
        }
        if (analysis.storageMode === "byPublicId") {
            onchange({});
        } else {
            const pid = publicId || boundImageId || "";
            onchange(setPointsForImage(value, pid, [], analysis));
        }
        expandedKey = null;
        if (armed) pointArming.disarm(armKey);
    }

    function commitPoints(pid: string, pts: (ImagePoint | null)[]) {
        if (!analysis) return;
        onchange(setPointsForImage(value, pid, pts, analysis));
    }

    function pointsFor(pid: string) {
        if (!analysis) return [] as (ImagePoint | null)[];
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
                <div class="image-group">
                    <div class="group-line">
                        {#if analysis.storageMode === "byPublicId"}
                            <span class="public-id" title={group.publicId}
                                >{group.publicId}</span
                            >
                            <span class="sep">:</span>
                        {/if}
                        <span class="count">{group.rows.length} pts</span>
                        <span class="paren">(</span>
                        {#each group.rows as row, i (rowKey(row))}
                            {#if i > 0}<span class="comma">, </span>{/if}
                            <button
                                type="button"
                                class="coord-chip"
                                class:expanded={expandedKey === rowKey(row)}
                                title={canEdit
                                    ? "Click to edit labels / coordinates"
                                    : formatCoord(row.pt) + extraPreview(row.pt)}
                                onclick={() => toggleExpand(row)}
                            >
                                {formatCoord(row.pt)}{#if extraPreview(row.pt)}<span
                                        class="extra-preview"
                                        >{extraPreview(row.pt)}</span
                                    >{/if}
                            </button>
                        {/each}
                        <span class="paren">)</span>
                    </div>

                    {#each group.rows as row (rowKey(row))}
                        {#if expandedKey === rowKey(row)}
                            <div class="editor">
                                <div class="editor-coords">
                                    <label>
                                        x
                                        <Input
                                            type="number"
                                            step="1"
                                            disabled={!canEdit}
                                            value={Math.round(row.pt.x)}
                                            oninput={(e) =>
                                                updatePointCoord(
                                                    row.publicId,
                                                    row.index,
                                                    "x",
                                                    (
                                                        e.currentTarget as HTMLInputElement
                                                    ).value,
                                                )}
                                        />
                                    </label>
                                    <label>
                                        y
                                        <Input
                                            type="number"
                                            step="1"
                                            disabled={!canEdit}
                                            value={Math.round(row.pt.y)}
                                            oninput={(e) =>
                                                updatePointCoord(
                                                    row.publicId,
                                                    row.index,
                                                    "y",
                                                    (
                                                        e.currentTarget as HTMLInputElement
                                                    ).value,
                                                )}
                                        />
                                    </label>
                                    {#if indexApplicable(row.pt)}
                                        <label
                                            title="B-scan index; empty = enface (null)"
                                        >
                                            i
                                            <Input
                                                type="number"
                                                step="1"
                                                disabled={!canEdit}
                                                value={typeof row.pt.index ===
                                                "number"
                                                    ? Math.round(row.pt.index)
                                                    : ""}
                                                placeholder="null"
                                                oninput={(e) =>
                                                    updatePointCoord(
                                                        row.publicId,
                                                        row.index,
                                                        "index",
                                                        (
                                                            e.currentTarget as HTMLInputElement
                                                        ).value,
                                                    )}
                                            />
                                        </label>
                                    {/if}
                                </div>

                                {#if hasExtras}
                                    <div class="editor-extras">
                                        {#each analysis.enumExtras as extra}
                                            <label>
                                                {extra.key}
                                                <select
                                                    disabled={!canEdit}
                                                    value={String(
                                                        row.pt[extra.key] ?? "",
                                                    )}
                                                    onchange={(e) =>
                                                        updatePointExtra(
                                                            row.publicId,
                                                            row.index,
                                                            extra.key,
                                                            (
                                                                e.currentTarget as HTMLSelectElement
                                                            ).value,
                                                        )}
                                                >
                                                    <option value="">—</option>
                                                    {#each extra.values as opt}
                                                        <option value={opt}
                                                            >{opt}</option
                                                        >
                                                    {/each}
                                                </select>
                                            </label>
                                        {/each}
                                        {#each stringExtraKeys as key}
                                            <label>
                                                {key}
                                                <Input
                                                    disabled={!canEdit}
                                                    value={String(
                                                        row.pt[key] ?? "",
                                                    )}
                                                    oninput={(e) =>
                                                        updatePointExtra(
                                                            row.publicId,
                                                            row.index,
                                                            key,
                                                            (
                                                                e.currentTarget as HTMLInputElement
                                                            ).value,
                                                        )}
                                                />
                                            </label>
                                        {/each}
                                    </div>
                                {/if}

                                <button
                                    type="button"
                                    class="collapse"
                                    onclick={() => (expandedKey = null)}
                                >
                                    Done
                                </button>
                            </div>
                        {/if}
                    {/each}
                </div>
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
    .image-group {
        display: flex;
        flex-direction: column;
        gap: 0.35em;
    }
    .group-line {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 0.15em 0.2em;
        font-family: monospace;
        font-size: 0.9em;
        line-height: 1.5;
    }
    .public-id {
        max-width: 12em;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        opacity: 0.85;
    }
    .sep,
    .paren,
    .comma,
    .count {
        opacity: 0.7;
    }
    .coord-chip {
        appearance: none;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 0.35em;
        color: inherit;
        cursor: pointer;
        font: inherit;
        padding: 0.05em 0.3em;
        margin: 0;
        transition:
            background-color 0.12s ease,
            border-color 0.12s ease;
    }
    .coord-chip:hover {
        background: color-mix(in srgb, currentColor 8%, transparent);
        border-color: color-mix(in srgb, currentColor 35%, transparent);
    }
    .coord-chip.expanded {
        background: color-mix(in srgb, currentColor 10%, transparent);
        border-color: color-mix(in srgb, currentColor 45%, transparent);
    }
    .extra-preview {
        opacity: 0.65;
        font-size: 0.9em;
    }
    .editor {
        display: flex;
        flex-direction: column;
        gap: 0.45em;
        margin-left: 0.25em;
        padding: 0.5em;
        border-left: 2px solid rgba(255, 255, 255, 0.25);
        background: rgba(255, 255, 255, 0.04);
    }
    .editor-coords,
    .editor-extras {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5em 0.75em;
        align-items: center;
    }
    .editor label {
        display: flex;
        align-items: center;
        gap: 0.35em;
        font-size: 0.9em;
    }
    .collapse {
        align-self: flex-start;
        appearance: none;
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 3px;
        color: inherit;
        cursor: pointer;
        font-size: 0.8em;
        padding: 0.15em 0.5em;
    }
    .collapse:hover {
        background: rgba(255, 255, 255, 0.08);
    }
</style>
