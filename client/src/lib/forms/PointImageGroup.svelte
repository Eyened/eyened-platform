<script lang="ts">
    import type {
        ImagePoint,
        PointStorageMode,
    } from "$lib/forms/pointSchema";
    import PointRowEditor, {
        type PointRow,
    } from "$lib/forms/PointRowEditor.svelte";

    interface Props {
        group: { publicId: string; rows: PointRow[] };
        storageMode: PointStorageMode;
        expandedKey: string | null;
        canEdit: boolean;
        hasExtras: boolean;
        enumExtras: { key: string; values: readonly string[] }[];
        stringExtraKeys: string[];
        formatCoord: (pt: ImagePoint) => string;
        extraPreview: (pt: ImagePoint) => string;
        rowKey: (row: PointRow) => string;
        indexApplicable: (pt: ImagePoint) => boolean;
        onToggleExpand: (row: PointRow) => void;
        onUpdateCoord: (
            pid: string,
            index: number,
            key: "x" | "y" | "index",
            raw: string,
        ) => void;
        onUpdateExtra: (
            pid: string,
            index: number,
            key: string,
            extraValue: string,
        ) => void;
        onCollapse: () => void;
    }

    let {
        group,
        storageMode,
        expandedKey,
        canEdit,
        hasExtras,
        enumExtras,
        stringExtraKeys,
        formatCoord,
        extraPreview,
        rowKey,
        indexApplicable,
        onToggleExpand,
        onUpdateCoord,
        onUpdateExtra,
        onCollapse,
    }: Props = $props();
</script>

<div class="image-group">
    <div class="group-line">
        {#if storageMode === "byPublicId"}
            <span class="public-id" title={group.publicId}>{group.publicId}</span
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
                onclick={() => onToggleExpand(row)}
            >
                {formatCoord(row.pt)}{#if extraPreview(row.pt)}<span
                        class="extra-preview">{extraPreview(row.pt)}</span
                    >{/if}
            </button>
        {/each}
        <span class="paren">)</span>
    </div>

    {#each group.rows as row (rowKey(row))}
        {#if expandedKey === rowKey(row)}
            <PointRowEditor
                {row}
                {canEdit}
                {hasExtras}
                {enumExtras}
                {stringExtraKeys}
                {indexApplicable}
                {onUpdateCoord}
                {onUpdateExtra}
                {onCollapse}
            />
        {/if}
    {/each}
</div>

<style>
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
</style>
