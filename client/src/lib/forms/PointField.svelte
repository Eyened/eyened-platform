<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import Location from "carbon-icons-svelte/lib/Location.svelte";
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import { formAnnotations, instances } from "$lib/data";
    import { eyeLabel, modalityField } from "$lib/workspace/imageMeta";
    import { formSchemas } from "$lib/data/stores.svelte";
    import { schemaName } from "$lib/forms/formTargets";
    import PointImageGroup, {
        type PointSlot,
    } from "$lib/forms/PointImageGroup.svelte";
    import PointRowEditor, {
        type PointRow,
    } from "$lib/forms/PointRowEditor.svelte";
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
    import { goToPoint } from "$lib/viewer/tools/PointTool.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getContext, onDestroy } from "svelte";
    import { viewportForImage } from "./formViewer";

    interface Props {
        schema: JSONSchema;
        value: unknown;
        onchange: (value: unknown) => void;
        canEdit?: boolean;
        fieldPath?: string;
        /** The question's words; defaults to the schema's title. */
        title?: string;
        required?: boolean;
        helperText?: string;
        invalidText?: string;
    }

    let {
        schema,
        value,
        onchange,
        canEdit = true,
        fieldPath = "point",
        title,
        required = false,
        helperText,
        invalidText,
    }: Props = $props();

    const uid = $props.id();
    const question = $derived(title ?? (schema.title || fieldPath));
    const note = $derived(invalidText ?? helperText);
    let fieldElement = $state<HTMLElement | null>(null);
    // Carbon: deleting more than one thing asks first.
    let removeAllOpen = $state(false);
    let placeButton = $state<HTMLElement | null>(null);

    const seedViewerContext = getContext<ViewerContext | undefined>(
        "viewerContext",
    );
    const formAnnotationId = getContext<number | undefined>(
        "pointFormAnnotationId",
    );
    const formName = $derived.by(() => {
        const annotation =
            formAnnotationId == null
                ? undefined
                : formAnnotations.get(formAnnotationId);
        const schema = annotation && formSchemas.get(annotation.form_schema_id);
        return `${schema ? schemaName(schema) : "Form"} #${formAnnotationId}`;
    });
    const boundImageId = getContext<string | undefined>("pointBoundImageId");
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const workspace = getContext<Workspace | undefined>("workspace");

    const pointMarker = $derived(
        mergeClientConfig(
            CLIENT_DEFAULTS,
            taskContext?.task.task_definition.config,
        ).point_marker,
    );

    const analysis = $derived(analyzePointSchema(schema));
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

    // Null slots stay, so numbers line up across the images of a matched-landmark list.
    const pointRows = $derived.by((): PointSlot[] => {
        if (!analysis) return [];
        if (analysis.addressing === "bare") {
            const pid = publicId || boundImageId || "";
            if (!pid) return [];
            return getPointsForImage(displayValue, pid, analysis).map(
                (pt, index) => ({
                    publicId: pid,
                    index,
                    pt,
                }),
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
        const rows: PointSlot[] = [];
        for (const id of ids.sort()) {
            for (const [index, pt] of getPointsForImage(
                displayValue,
                id,
                analysis,
            ).entries()) {
                rows.push({ publicId: id, index, pt });
            }
        }
        return rows;
    });

    const pointCount = $derived(pointRows.filter((r) => r.pt).length);

    type ImageGroup = { publicId: string; rows: PointSlot[] };

    // An image without a point yet gets no heading.
    const imageGroups = $derived.by((): ImageGroup[] => {
        const byId: Record<string, PointSlot[]> = {};
        for (const row of pointRows) {
            (byId[row.publicId] ??= []).push(row);
        }
        return Object.entries(byId)
            .filter(([, rows]) => rows.some((r) => r.pt))
            .map(([pid, rows]) => ({ publicId: pid, rows }));
    });

    /** The image in viewer words; its public ID when the viewer doesn't know it. */
    function imageHeading(pid: string): string {
        const meta = instances.get(pid);
        if (!meta) return pid;
        return (
            [eyeLabel(meta.laterality), modalityField(meta), meta.study.date]
                .filter(Boolean)
                .join(" · ") || pid
        );
    }

    /** Show i only for oct-space fields that carry an OCT index (number or null). */
    function indexApplicable(pt: ImagePoint): boolean {
        if (analysis?.coordinateSpace === "enface2d") return false;
        return "index" in pt;
    }

    /** Volume schemas require a numeric index; only `oct` allows blank → null. */
    const allowNullIndex = $derived(analysis?.coordinateSpace === "oct");

    function bscanText(pt: ImagePoint): string | null {
        if (!indexApplicable(pt)) return null;
        return typeof pt.index === "number"
            ? `B-scan ${Math.round(pt.index)}`
            : "en-face";
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

    function rowKey(row: { publicId: string; index: number }) {
        return `${row.publicId}:${row.index}`;
    }

    /** Closes the editor and puts focus back on its row. */
    function collapse() {
        const key = expandedKey;
        expandedKey = null;
        queueMicrotask(() =>
            [
                ...(fieldElement?.querySelectorAll<HTMLElement>(
                    "[data-row-key]",
                ) ?? []),
            ]
                .find((b) => b.dataset.rowKey === key)
                ?.focus(),
        );
    }

    let hint = $state<string | null>(null);

    /** A row opens its editor and goes to the point in the viewport showing its image. */
    function goTo(row: PointRow) {
        expandedKey = rowKey(row);
        // On /browse there is no viewer to go to, so no hint either.
        if (!workspace) return;
        const layers = viewportForImage(
            workspace,
            row.publicId,
            typeof row.pt.index === "number",
        );
        hint = layers ? null : "Open this image in the viewer first.";
        if (!layers) return;
        goToPoint(row.pt, layers.viewerContext);
        // The armed field's tool marks the point current, so [ ] step on from it.
        if (armed && layers.formPointTool)
            layers.formPointTool.current = row.index;
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
                label: question,
                form: formName,
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
        if (analysis.addressing === "byImage") {
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

    /** Omit the field from form_data (undefined), not an empty list — for optional fields. */
    function removeField() {
        if (liveSession) {
            liveSession.fieldValue = undefined;
            liveSession.persist();
        } else {
            onchange(undefined);
        }
        expandedKey = null;
        if (armed) pointArming.disarm(armKey);
    }

    const fieldPresent = $derived(displayValue !== undefined);

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
            // volume: index is required; blanking would strand the marker.
            // The editor shows the error; a volume point keeps its stored B-scan.
            if (analysis?.coordinateSpace === "volume") return;
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
            deletePointAt(pointsFor(pid), index, analysis.sparse),
        );
        expandedKey = null;
    }
</script>

<div
    bind:this={fieldElement}
    role="group"
    aria-labelledby="{uid}-legend"
    aria-describedby={note ? `${uid}-note` : undefined}
    class="flex flex-col gap-3"
>
    <!-- Always mounted, so a new hint is announced. -->
    <p role="status" class="sr-only">{hint ?? ""}</p>
    <div class="flex items-start gap-2">
        <div class="min-w-0 flex-1">
            <p id="{uid}-legend" class="text-label-01 text-text-secondary">
                {required ? `${question} (required)` : question}
            </p>
            {#if note}
                <p
                    id="{uid}-note"
                    class="mt-1 text-helper-text-01 {invalidText
                        ? 'text-text-error'
                        : 'text-text-helper'}"
                >
                    {note}
                </p>
            {/if}
        </div>
        {#if canEdit && fieldPresent}
            <IconButton
                size="icon-xs"
                label="Clear answer: {question}"
                data-clear
                onclick={removeField}><Close /></IconButton
            >
        {/if}
    </div>

    {#if !isPointWidget(schema) || !analysis}
        <p class="text-helper-text-01 text-text-error">
            Point widget misconfigured for this schema.
        </p>
    {:else}
        {@const single = analysis.cardinality === "single"}
        {#if canEdit}
            <div class="flex flex-wrap items-center gap-2">
                {#if seedViewerContext}
                    <Button
                        bind:ref={placeButton}
                        size="sm"
                        variant={armed ? "default" : "outline"}
                        aria-pressed={armed}
                        disabled={!canActivate}
                        onclick={toggleActivate}
                        >{armed
                            ? "Stop placing"
                            : single
                              ? pointCount
                                  ? "Move"
                                  : "Place"
                              : "Place points"}<Location /></Button
                    >
                {:else}
                    <p class="text-helper-text-01 text-text-helper">
                        No viewer — tool unavailable
                    </p>
                {/if}
                {#if !single && pointCount >= 2}
                    <Button
                        size="sm"
                        variant="ghost"
                        onclick={() => (removeAllOpen = true)}
                        >Remove all</Button
                    >
                {/if}
            </div>
        {/if}

        {#if single && analysis.addressing === "bare"}
            {@const slot = pointRows.find((r) => r.pt)}
            {#if slot?.pt}
                {@const row: PointRow = { publicId: slot.publicId, index: slot.index, pt: slot.pt }}
                <button
                    type="button"
                    data-row-key={rowKey(row)}
                    aria-expanded={expandedKey === rowKey(row)}
                    class="self-start text-body-compact-01 text-link-primary hover:underline"
                    onclick={() => goTo(row)}
                    >{Math.round(row.pt.x)}, {Math.round(row.pt.y)}{bscanText(
                        row.pt,
                    )
                        ? ` · ${bscanText(row.pt)}`
                        : ""}</button
                >
                {#if expandedKey === rowKey(row)}
                    <PointRowEditor
                        {row}
                        number={1}
                        {canEdit}
                        {hasExtras}
                        enumExtras={analysis.enumExtras}
                        {stringExtraKeys}
                        {indexApplicable}
                        {allowNullIndex}
                        {hint}
                        onUpdateCoord={updatePointCoord}
                        onUpdateExtra={updatePointExtra}
                        onRemove={() => removePoint(row.publicId, row.index)}
                        onCollapse={collapse}
                    />
                {/if}
            {:else}
                <p class="text-body-compact-01 text-text-secondary">
                    Not placed
                </p>
            {/if}
        {:else if imageGroups.length === 0}
            <p class="text-body-compact-01 text-text-secondary">No points</p>
        {:else}
            {#each imageGroups as group (group.publicId)}
                <PointImageGroup
                    {group}
                    heading={imageHeading(group.publicId)}
                    {expandedKey}
                    {canEdit}
                    {hasExtras}
                    enumExtras={analysis.enumExtras}
                    {stringExtraKeys}
                    {rowKey}
                    {bscanText}
                    {extraPreview}
                    {indexApplicable}
                    {allowNullIndex}
                    {hint}
                    onGoTo={goTo}
                    onUpdateCoord={updatePointCoord}
                    onUpdateExtra={updatePointExtra}
                    onRemovePoint={removePoint}
                    onCollapse={collapse}
                />
            {/each}
        {/if}
    {/if}
</div>

<Modal
    bind:open={removeAllOpen}
    danger
    size="xs"
    modalHeading="Remove all points"
    modalLabel={question}
    primaryButtonText="Remove all"
    primaryButtonLoadingDescription="Removing…"
    successDescription="Removed"
    errorTitle="Points could not be removed"
    onsubmit={async () => clear()}
    onCloseAutoFocus={(event) => {
        // Remove all is gone with the points, so focus goes to Place points.
        if (pointCount === 0) {
            event.preventDefault();
            placeButton?.focus();
        }
    }}
>
    <p>Removes every point of this question. This can't be undone.</p>
</Modal>
